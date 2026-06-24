# iMocha AI Presentation Studio

Monorepo. Place this file at the repo root and run Claude Code from the repo root.

## Repo layout
- `Front-End/` — React/Vite/TS frontend (already built; talks to the backend via a typed API client).
- `Back-End/` — FastAPI backend. **This is what we're building.**
- `assets/` — real iMocha brand assets, shared by both:
  - `icons/`, `infographics/`, `logo/`, `mockups/`, `templates/`
  - `_infographics_manifest.*`, `_mockups_manifest.*` — catalogs of those assets
  - `logo.png`, `logo_white.png`, `logo_footer.png`, `cover_bg.jpg`
- `docs/` — `architecture.md` is the **source of truth** (read it before planning).

## The contract
- `docs/architecture.md` §7 = data models, §8 = API endpoints. This is the contract
  with the frontend. Backend Pydantic models must mirror §7 (these match
  `Front-End/src/types.ts` — confirm that path on first read).
- Do not change the contract without updating both `docs/architecture.md` and the
  frontend. If this file/the docs and the code disagree, the docs win until updated.

## Use the real assets — don't invent
- Build the iMocha PPTX template from `assets/templates/` and the logos in `assets/`
  (`logo.png`, `logo_white.png`, `logo_footer.png`, `cover_bg.jpg`).
- Seed the asset library / retrieval from `assets/icons/`, `assets/infographics/`,
  using the manifests in `assets/` as the metadata source where present.

## Architecture rules (non-negotiable — full detail in docs/architecture.md §2,§4)
- LLM only for judgment (understand/classify/plan, compose). Everything with one
  correct answer is deterministic code: parse, retrieve/rank, brand-lint,
  content-diff, export.
- Compliance by construction: the composer builds only from approved template
  primitives; brand correctness is then VERIFIED by a deterministic linter, never by
  an LLM grading itself.
- Content preservation = claim-level fidelity, verified by a deterministic diff.
- Bounded retries: max 2 regenerations per slide, then flag. No unbounded loops.
- The job state machine PAUSES at `plan_ready` until `/plan/approve` is called.

## Stack (see docs/architecture.md §12)
FastAPI · Pydantic v2 · PostgreSQL + pgvector · python-pptx (PPTX builder; infographic
fragment merging via XML-level shape-tree copy) · LibreOffice headless (PDF export +
slide preview PNG) · Celery/RQ + Redis · enterprise/zero-retention LLM (Azure OpenAI
or Bedrock) behind one provider interface. No Supabase.

## How to work
- Plan before coding on any multi-file change; wait for my approval of the plan.
- After each change, run tests + type checks and SHOW the command and its output.
  Don't claim success without evidence.
- Commit each working increment with a clear message.
- One task per session; tell me when context is getting full so we can clear.
- Before building the AI agents, prove the walking skeleton (docs §14): a real deck
  in → editable, on-brand PPTX/PDF out, through the real API. Gate: python-pptx
  shape-tree copy produces editable merged PPTX AND LibreOffice headless exports
  a usable PDF with correct fonts. If either fails, STOP and tell me before continuing.

## Commands (Back-End/ — adjust once scaffolded)
- Run server: `cd Back-End && uvicorn app.main:app --reload`
- Tests: `cd Back-End && pytest -q`
- Lint/types: `cd Back-End && ruff check . && mypy app`