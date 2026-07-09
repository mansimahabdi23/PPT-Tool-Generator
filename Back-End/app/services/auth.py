"""OIDC JWT authentication and RBAC for FastAPI routes.

How it works
------------
* ``get_current_user`` is a FastAPI dependency injected into every protected
  route.  It validates the Bearer token using Azure Entra ID's JWKS endpoint,
  returning a ``UserIdentity``.

* ``require_roles(*roles)`` is a dependency factory that raises HTTP 403 unless
  the current user holds at least one of the listed roles.

* Dev bypass: when ``settings.auth_dev_bypass`` is ``True`` (never in
  production), ``get_current_user`` returns a synthetic IT-admin identity so
  the server is usable without a real IdP.

Production environment variables::

    OIDC_AUTHORITY=https://login.microsoftonline.com/{tenant_id}/v2.0
    OIDC_AUDIENCE=api://{client_id}
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException
from jwt.algorithms import RSAAlgorithm

from app.config import settings
from app.models.auth import Role, UserIdentity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWKS-backed JWT validator
# ---------------------------------------------------------------------------

_VALIDATOR: OIDCValidator | None = None
_VALIDATOR_LOCK = threading.Lock()


class OIDCValidator:
    """Validates Azure Entra ID RS256 JWTs with a JWKS cache."""

    def __init__(self, authority: str, audience: str, cache_ttl: int = 3600) -> None:
        self._authority = authority.rstrip("/")
        self._audience = audience
        self._cache_ttl = cache_ttl
        self._keys: dict[str, Any] = {}       # kid → RSA public key object
        self._fetched_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _refresh_keys(self) -> None:
        """Fetch JWKS from the IdP. Must be called with ``self._lock`` held."""
        config_url = f"{self._authority}/.well-known/openid-configuration"
        with urllib.request.urlopen(config_url, timeout=10) as resp:  # noqa: S310
            config: dict[str, Any] = json.loads(resp.read())
        jwks_uri: str = config["jwks_uri"]
        with urllib.request.urlopen(jwks_uri, timeout=10) as resp:  # noqa: S310
            jwks: dict[str, Any] = json.loads(resp.read())
        self._keys = {
            k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k))
            for k in jwks.get("keys", [])
            if k.get("use") == "sig"
        }
        self._fetched_at = time.monotonic()
        logger.info("OIDC: loaded %d signing keys from %s", len(self._keys), jwks_uri)

    def _ensure_keys(self) -> None:
        """Refresh JWKS cache if expired. Must be called with ``self._lock`` held."""
        if time.monotonic() - self._fetched_at < self._cache_ttl and self._keys:
            return
        try:
            self._refresh_keys()
        except Exception as exc:
            if self._keys:
                # Keep serving stale keys on transient network errors.
                logger.warning("OIDC: JWKS refresh failed (using stale keys): %s", exc)
            else:
                raise ValueError(f"OIDC: JWKS unavailable: {exc}") from exc

    # ------------------------------------------------------------------
    # Token validation
    # ------------------------------------------------------------------

    def validate(self, token: str) -> UserIdentity:
        """Decode and validate *token*.

        Raises
        ------
        ValueError
            On any auth failure (malformed token, expired, wrong issuer, etc.).
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise ValueError(f"Malformed JWT: {exc}") from exc

        kid: str = header.get("kid", "")
        with self._lock:
            self._ensure_keys()
            key = self._keys.get(kid)

        if key is None:
            raise ValueError(f"Unknown signing key id: {kid!r}")

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._authority,
            )
        except jwt.ExpiredSignatureError as exc:
            raise ValueError("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Invalid token: {exc}") from exc

        # Azure Entra ID app roles arrive in the "roles" claim as list[str].
        raw_roles: list[str] = payload.get("roles", [])
        roles: tuple[Role, ...] = tuple(
            r for raw in raw_roles for r in (_safe_role(raw),) if r is not None
        )

        return UserIdentity(
            user_id=payload.get("oid") or payload.get("sub", ""),
            email=payload.get("preferred_username") or payload.get("email", ""),
            name=payload.get("name", ""),
            roles=roles,
        )


def _safe_role(raw: str) -> Role | None:
    try:
        return Role(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

def _get_validator() -> OIDCValidator:
    global _VALIDATOR
    if _VALIDATOR is None:
        with _VALIDATOR_LOCK:
            if _VALIDATOR is None:
                _VALIDATOR = OIDCValidator(
                    authority=settings.oidc_authority,
                    audience=settings.oidc_audience,
                    cache_ttl=settings.oidc_jwks_cache_ttl_seconds,
                )
    return _VALIDATOR


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_DEV_IDENTITY = UserIdentity(
    user_id="dev-bypass",
    email="dev@imocha.io",
    name="Dev Bypass (IT-admin)",
    roles=(Role.it_admin,),
)


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> UserIdentity:
    """FastAPI dependency — validates Bearer token and returns ``UserIdentity``.

    When ``settings.auth_dev_bypass`` is ``True`` (local dev only, never prod),
    skips token validation and returns a synthetic IT-admin identity.
    """
    if settings.auth_dev_bypass:
        return _DEV_IDENTITY

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Authorization header must be 'Bearer <token>'",
        )

    try:
        return _get_validator().validate(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("OIDC: unexpected validation error: %s", exc)
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc


def require_roles(*roles: Role) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces role membership.

    Raises HTTP 403 unless the current user holds at least one of *roles*.
    """
    async def _guard(
        user: Annotated[UserIdentity, Depends(get_current_user)],
    ) -> UserIdentity:
        if not user.has_role(*roles):
            names = ", ".join(str(r) for r in roles)
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {names}",
            )
        return user

    return _guard
