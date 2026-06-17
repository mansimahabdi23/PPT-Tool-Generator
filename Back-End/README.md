# iMocha AI Presentation Studio — Backend

FastAPI backend. Managed with [uv](https://github.com/astral-sh/uv).

## Setup

```bash
cd Back-End
uv sync --extra dev
```

## Commands

| Task | Command |
|---|---|
| Run dev server | `uv run uvicorn app.main:app --reload` |
| Run tests | `uv run python -m pytest -q` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type-check | `uv run mypy app` |

The server starts at `http://localhost:8000`.  
OpenAPI docs: `http://localhost:8000/docs`  
Health check: `GET http://localhost:8000/health`

All API endpoints are under `/api` — see `docs/architecture.md §8` for the contract.
