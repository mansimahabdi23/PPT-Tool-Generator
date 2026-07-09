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


settings = Settings()
