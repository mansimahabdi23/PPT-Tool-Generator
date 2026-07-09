"""Application settings — loaded from environment variables (or .env file)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is three levels above this file: Back-End/app/config.py → Back-End/app/ → Back-End/ → repo root
_REPO_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    debug: bool = False

    # Monorepo assets/ directory (override via ASSETS_ROOT env var if needed)
    assets_root: Path = _REPO_ROOT / "assets"

    # PostgreSQL + pgvector connection string (optional).
    # When set, PostgresAssetStore is used in production; otherwise InMemoryAssetStore.
    # Example: postgresql://user:pass@localhost:5432/imocha
    database_url: str | None = None

    # ---------------------------------------------------------------------------
    # Job engine
    # ---------------------------------------------------------------------------
    # "in_process" runs jobs in a ThreadPoolExecutor inside this process.
    # The documented prod upgrade path: swap for a CeleryJobEngine or RQJobEngine
    # that implements the same JobEngine.submit() seam — no caller changes.
    job_engine: str = "in_process"
    job_engine_workers: int = 2

    # Maximum number of compose→validate cycles before a job is marked partial.
    max_regenerations: int = 2

    # ---------------------------------------------------------------------------
    # LLM provider
    # ---------------------------------------------------------------------------
    # "stub" (default) — deterministic, offline, testable; no API calls.
    # "azure_openai"  — real Azure OpenAI chat completions; requires the three
    #                   AZURE_OPENAI_* vars below to be set in the environment.
    llm_provider: str = "stub"

    # Azure OpenAI connection — required when llm_provider="azure_openai".
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-08-01-preview"

    # ---------------------------------------------------------------------------
    # Enterprise: Authentication (OIDC / Azure Entra ID)
    # ---------------------------------------------------------------------------
    # Set AUTH_DEV_BYPASS=true for local development only — NEVER in production.
    auth_dev_bypass: bool = False

    # Azure Entra ID (or generic OIDC) authority and audience.
    # Example:
    #   OIDC_AUTHORITY=https://login.microsoftonline.com/{tenant_id}/v2.0
    #   OIDC_AUDIENCE=api://{client_id}
    oidc_authority: str = ""
    oidc_audience: str = ""
    oidc_jwks_cache_ttl_seconds: int = 3600

    # ---------------------------------------------------------------------------
    # Enterprise: Data retention
    # ---------------------------------------------------------------------------
    # Output files (PPTX/PDF) and intermediates are deleted after this many days.
    # IT-admin can trigger a sweep early via POST /api/admin/purge.
    data_retention_days: int = 30

    # ---------------------------------------------------------------------------
    # Enterprise: LLM region pinning (zero-retention tier)
    # ---------------------------------------------------------------------------
    # When llm_provider="azure_openai", AZURE_OPENAI_DATA_ZONE must be set to one
    # of the approved regions to prevent data leaving the allowed geography.
    azure_openai_allowed_regions: list[str] = ["eastus", "westeurope"]
    azure_openai_data_zone: str = ""


settings = Settings()
