"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import assets, files, jobs
from app.services.asset_store import InMemoryAssetStore, init_store
from app.services.seeder import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Seed the asset library from disk (infographics + icons).
    # Runs at startup; a failed seed is non-fatal — the store stays empty.
    store = InMemoryAssetStore()
    n = seed_all(settings.assets_root, store)
    init_store(store)
    print(f"[startup] Asset library seeded: {n} records ({store.count()} total)")
    yield
    # Shutdown — nothing to clean up for the in-memory store.


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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
