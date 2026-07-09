"""Auth models — Role enum and UserIdentity."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    user = "user"
    reviewer = "reviewer"
    brand_admin = "brand-admin"
    it_admin = "it-admin"


@dataclass(frozen=True)
class UserIdentity:
    """Decoded, validated identity from an OIDC JWT."""

    user_id: str
    email: str
    name: str
    roles: tuple[Role, ...] = field(default_factory=tuple)

    def has_role(self, *roles: Role) -> bool:
        """Return True if the user holds ANY of the given roles."""
        return bool(set(self.roles) & set(roles))
