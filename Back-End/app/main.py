"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, assets, files, jobs
from app.services.asset_store import InMemoryAssetStore, init_store
from app.services.audit import AuditLogger, init_audit_logger
from app.services.job_engine import InProcessJobEngine, init_engine
from app.services.llm_provider import (
    AzureOpenAIProvider,
    LLMProvider,
    StubProvider,
    init_provider,
)
from app.services.seeder import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Seed the asset library from disk (infographics + icons).
    # Runs at startup; a failed seed is non-fatal — the store stays empty.
    store = InMemoryAssetStore()
    n = seed_all(settings.assets_root, store)
    init_store(store)
    print(f"[startup] Asset library seeded: {n} records ({store.count()} total)")

    # Initialise the job engine (in-process thread pool by default).
    # Prod upgrade: swap InProcessJobEngine for CeleryJobEngine / RQJobEngine
    # without changing any caller — they all go through get_engine().
    engine = InProcessJobEngine(max_workers=settings.job_engine_workers)
    init_engine(engine)
    print(f"[startup] Job engine: InProcessJobEngine (workers={settings.job_engine_workers})")

    # Initialise the LLM provider.
    # Prod upgrade: set LLM_PROVIDER=azure_openai + AZURE_OPENAI_* env vars.
    provider: LLMProvider
    if settings.llm_provider == "azure_openai" and settings.azure_openai_endpoint:
        from openai import AzureOpenAI
        az_client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        provider = AzureOpenAIProvider(az_client, settings.azure_openai_deployment)
        print(f"[startup] LLM provider: AzureOpenAI (deployment={settings.azure_openai_deployment})")
    else:
        provider = StubProvider()
        print("[startup] LLM provider: StubProvider (deterministic offline mode)")
    init_provider(provider)

    # Region pinning check — prevent data leaving the approved geography.
    if (
        settings.llm_provider == "azure_openai"
        and settings.azure_openai_data_zone
        and settings.azure_openai_data_zone not in settings.azure_openai_allowed_regions
    ):
        raise RuntimeError(
            f"AZURE_OPENAI_DATA_ZONE={settings.azure_openai_data_zone!r} is not in "
            f"allowed regions {settings.azure_openai_allowed_regions}. "
            "Set AZURE_OPENAI_DATA_ZONE to an approved region before starting."
        )

    # Initialise the audit logger.
    init_audit_logger(AuditLogger())
    if settings.auth_dev_bypass:
        print("[startup] Auth: dev bypass ENABLED (IT-admin identity injected)")
    else:
        print(f"[startup] Auth: OIDC enabled (authority={settings.oidc_authority!r})")

    yield

    # Shutdown — drain the thread pool before the process exits.
    engine.shutdown(wait=True)
    print("[shutdown] Job engine drained.")


app = FastAPI(
    title="iMocha AI Presentation Studio",
    description="Backend API for transforming PowerPoint decks into on-brand iMocha presentations.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server (and any configured origins)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(assets.router, prefix=settings.api_prefix)
app.include_router(files.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
