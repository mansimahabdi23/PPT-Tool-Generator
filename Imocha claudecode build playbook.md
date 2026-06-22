# Driving the iMocha backend build with Claude Code

A practical playbook: set up project memory once, then feed Claude Code one well-structured prompt per step. Built around the six-step, risk-first backend plan (contract → template → walking skeleton → deterministic services → job engine + agents → enterprise hardening).

---

## 0. Set up project memory FIRST (do this before any feature prompt)

The biggest predictor of success isn't the prompt — it's the persistent context. Two things to do once:

**a) Put your reference docs in the repo.** Create a `/docs` folder and drop in: the frontend Lovable spec (markdown), a short `architecture.md` (the LLM-vs-deterministic split + the pipeline + the API endpoint list), and the brand tokens. Reference these from CLAUDE.md — don't paste them inline everywhere.

**b) Create a lean `CLAUDE.md` at the repo root.** Keep it short (a focused set of rules, not an essay — Claude skims past bloated files). Paste this into Claude Code:

```
Create a CLAUDE.md at the repo root with these contents. Keep it concise.

# iMocha AI Presentation Studio — Backend

## What this is
A FastAPI backend that transforms an uploaded PowerPoint into an on-brand,
fully editable iMocha deck (PPTX + PDF). The React frontend already exists in
/frontend and talks to us via a typed API client (see /docs/architecture.md).

## Architecture rules (non-negotiable)
- LLM only for judgment (understand/classify/plan, compose). Everything with one
  correct answer is deterministic code: parsing, asset retrieval/ranking,
  brand-lint, content-diff, export.
- Compliance by construction: the composer builds from approved template
  primitives only. Brand correctness is then VERIFIED by a deterministic linter,
  never by an LLM grading itself.
- Content preservation = claim-level fidelity, verified by a deterministic text
  diff. Never self-graded by the model.
- Bounded retries: max 2 regenerations per slide, then flag. No unbounded loops.

## Stack
FastAPI · Pydantic v2 · PostgreSQL + pgvector · Aspose.Slides (PPTX backbone) ·
Celery/RQ + Redis (workers) · an enterprise/zero-retention LLM (Azure OpenAI or
Bedrock) behind a single provider interface. No Supabase.

## The API contract
The endpoints in /docs/architecture.md are the contract with the frontend.
Pydantic models must mirror the TypeScript interfaces in
/frontend/src/types.ts. Do not change the contract without updating both sides.

## How to work
- Plan before coding on any multi-file change; wait for my approval of the plan.
- After each change, run the tests and the type checker and SHOW me the output.
  Don't claim success without showing the command and its result.
- Commit each working increment with a clear message.
- One task per session. Tell me when context is getting full so we can clear.

## Commands
- Run server: `uvicorn app.main:app --reload`
- Tests: `pytest -q`
- Lint/types: `ruff check . && mypy app`
```

Then run `/init` if you like (it augments CLAUDE.md by scanning the repo), and review what it adds.

> Tip: you can also add a domain-specific `app/api/CLAUDE.md` later with endpoint conventions. Reference docs, don't inline them.

---

## 1. The repeatable prompt pattern (use this shape for EVERY step)

Each step is two prompts: a **plan** prompt (in plan mode), then an **implement** prompt.

**Plan prompt** — enter plan mode (Shift+Tab twice), then:
```
Read [specific files/dirs]. Goal: [one sentence].
Constraints: [the rules that apply].
Produce a detailed implementation plan: files to create/change, the data flow,
and how you'll test it. Ask me any clarifying questions first. Do not write code yet.
```
Review the plan in your editor (Ctrl+G), correct misunderstandings, then approve.

**Implement prompt** — switch out of plan mode:
```
Implement the approved plan. Write tests as you go. When done, run the tests and
the type checker and show me the exact commands and their output. Then commit.
```

Five habits that make this work: plan-before-code on anything multi-file; demand evidence (test output / real responses), never trust "done"; one step per session and `/clear` between them; paste a real reference (e.g. an existing route, or `frontend/src/lib/api.ts`) rather than describing it; commit every working increment.

---

## 2. The six steps as Claude Code prompts

Work top to bottom. Each builds on the last. Don't skip ahead — steps 2–3 are the gate that de-risks the whole project.

### Step 1 — Freeze the API contract
**Plan:**
```
[plan mode] Read Front-End/src/types.ts and docs/architecture.md. Goal: scaffold
a FastAPI app whose Pydantic models exactly mirror the frontend TypeScript types
(TransformJob, SlidePlan, TransformedSlide, BrandAsset, and the JobStatus enum),
and stub every endpoint from the contract returning typed placeholder data.
Plan the project structure (app/, models, routers, services, tests). No real logic
yet. Ask questions, then give me the plan.
```
**Implement:**
```
Implement the plan. Stub endpoints return realistic placeholder data matching the
types. Generate the OpenAPI schema and add a test that asserts the response shapes
match the contract. Run uvicorn, hit /docs, show me the schema and the passing
tests, then commit.
```
*Done when:* the server runs, `/docs` shows every contract endpoint, and shape tests pass.

### Step 2 — Build the iMocha master template
**Plan:**
```
[plan mode] Read /docs/architecture.md (brand tokens) and look at the slide
mockups in /docs/slide-previews. Goal: create a reusable iMocha PPTX template
(theme: fonts Playfair Display titles / Poppins body, the brand color palette,
gradient rules) with named layouts for each slide type: title, agenda, content,
data, divider, closing. Plan how the template is stored and loaded by Aspose, and
a script that emits one sample slide per layout so I can eyeball it. Give me the plan.
```
**Implement:**
```
Implement it. Produce a sample.pptx with one slide per layout. Export it to PNGs
and show them to me. Commit the template and the generation script.
```
...Note: infographics are prebuilt editable PPTX fragments in assets/infographics/
(not images) — the template must define a content layout/region they can be merged
into, not an image placeholder.

*Done when:* sample slides open in PowerPoint, on-brand, with editable elements.

### Step 3 — Walking skeleton (the de-risking gate)
**Plan:**
```
[plan mode] Goal: prove the end-to-end path with NO AI yet. Upload a .pptx ->
extract its text deterministically -> place that text into the matching iMocha
template layouts -> export editable PPTX + PDF -> return download URLs. Wire this
through the REAL API for the upload and result endpoints only (leave plan/review
mocked). This is the highest-risk part: confirm Aspose produces faithful, EDITABLE
output (editable text, and at least one editable chart). Plan it and list the
fidelity risks you'll check.
```
**Implement:**
```
Implement the skeleton. Add an integration test that uploads a real sample deck and
asserts a valid PPTX comes back. Open the output and confirm elements are editable;
show me screenshots/evidence. If anything can't be made editable via Aspose, STOP
and tell me exactly what and why before continuing. Commit.
```
*Done when:* a real deck goes in and an editable, on-brand deck comes out, through the real API. **If this fails, fix it before anything else — the rest is incremental.**

### Step 4 — Deterministic services
Do these as separate sessions (one each), same plan/implement pattern:
```
Build the parser: produce a normalized slide model from the upload — text, tables,
images, geometry, and atomic claims with their source slide/shape location. Tests
over sample decks. Show output, commit.
```
```
Build the asset library + retrieval. Postgres + pgvector. BrandAsset metadata per
/docs (type, slot, dimensions, max-items, approval status, version). Retrieval =
deterministic filter (approved + correct slot + fits item-count/dimensions) THEN
vector rank. Only approved assets are ever indexed. Tests, evidence, commit.
```
```
Build the three validators as pure functions: brand-lint (fonts/colors/logo/
gradients vs allow-list, returns exact violations), content-diff (every source
claim/number present and unaltered in output), layout QA (overflow/alignment/
missing assets). Each returns structured pass/fail + details. Tests, commit.
```

### Step 5 — Job engine + the two LLM agents
**Plan first** (this is the biggest step):
```
[plan mode] Goal: add an async job engine (Celery or RQ + Redis) and a job state
machine that walks the pipeline (parse -> analyze&plan -> PLAN_READY [pause] ->
retrieve -> compose -> validate [retry<=2] -> export -> completed) updating
JobStatus so the frontend's getJob polling reflects progress. The state machine
PAUSES at plan_ready until /plan/approve is called. Then wire two LLM steps behind
the provider interface: Analyze&Plan (produces SlidePlan[]) and a
template-constrained Compose. Keep brand-lint/content-diff as the deterministic
gate after compose. Plan the state machine, the pause/resume, and failure handling.
```
**Implement** in sub-increments (don't do it all at once): state machine + status updates first (still using the skeleton's dumb transform), verify the frontend's processing + plan screens light up against the real backend; then swap in Analyze & Plan; then swap in Compose; run the validators after each. Show evidence and commit after each sub-increment.

### Step 6 — Enterprise hardening (before any real customer data)
```
Add SSO (OIDC), role-based access (user/brand-admin/reviewer/IT-admin), an audit
log of every job (who, what, assets/versions used, approvals), and a data-retention/
deletion policy for uploads, intermediates and outputs. Switch the LLM provider to a
zero-retention enterprise tier (Azure OpenAI or Bedrock) with region pinning. Tests,
evidence, commit.
```
Do this before feeding it any real deck — uploaded decks contain confidential customer data.

---

## 3. Keeping sessions healthy
- One step (or sub-increment) per session; `/clear` between them. A fresh session already spends ~20k tokens on system prompt + CLAUDE.md before you type.
- When context passes ~60%, use the Document & Clear pattern: ask Claude to write progress + decisions to a markdown file in /docs, `/clear`, then start the next session by reading that file.
- When a fix is mediocre, don't patch it — say "knowing what you know now, scrap this and implement the clean version."
- Before merging anything important: "diff this branch against main, then grill me on these changes and prove the validators still pass — don't open a PR until I'm satisfied."

---

## 4. What to hand Claude Code on day one
1. The repo with `/frontend` in it.
2. `/docs/architecture.md` — the pipeline, the LLM-vs-deterministic table, and the API endpoint list (the contract).
3. `/docs/slide-previews/` — the before/after PNGs, so the template step has a visual target.
4. The CLAUDE.md from Section 0.

Then start with the Step 1 plan prompt. Resist the urge to ask for the whole backend in one prompt — the value of this sequence is that each step is verifiable before the next one depends on it.