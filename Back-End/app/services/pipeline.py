"""State-machine pipeline — two segments separated by the plan_ready pause.

Segment A  (triggered by POST /jobs, submitted to engine):
  parsing → parse() → analyzing → planner.build_plan() → plan_ready  [STOP]

Segment B  (triggered by POST /jobs/{id}/plan/approve, submitted to engine):
  retrieving → composing → compose() → validating → [validate gate, retry ≤ N]
             → exporting → export() → completed

Any unhandled exception in either segment transitions the job to ``failed``
with the exception message stored on the record for the frontend to display.

The ``ParsedDeck`` from segment_a is kept on the ``JobRecord._parsed`` field
so segment_b does not re-parse the file.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from app.config import settings
from app.models.enums import ApprovalState, AssetSlot, AssetType, JobStatus, SlideType
from app.models.job import SlidePlan, TransformedSlide
from app.services import store as job_store
from app.services.asset_store import get_store
from app.services.brand_lint import lint
from app.services.composer import compose
from app.services.content_diff import ContentDiffResult, diff
from app.services.exporter import OUT_ROOT, export, render_previews
from app.services.layout_qa import check as layout_check
from app.services.parser import ParsedDeck, parse
from app.services.planner import build_plan
from app.services.slide_result import build_slides

# ---------------------------------------------------------------------------
# Asset-retrieval helpers
# ---------------------------------------------------------------------------

# Maps each slide type to the asset slot that matches its role in the deck.
_SLIDE_TYPE_TO_SLOT: dict[SlideType, AssetSlot] = {
    SlideType.title:   AssetSlot.cover,
    SlideType.agenda:  AssetSlot.content,
    SlideType.content: AssetSlot.content,
    SlideType.data:    AssetSlot.content,
    SlideType.divider: AssetSlot.divider,
    SlideType.closing: AssetSlot.closing,
}

# Asset types that don't have a queryable store record (they come from
# template primitives or brand files, not the asset library).
_LIBRARY_ASSET_TYPES: frozenset[AssetType] = frozenset({
    AssetType.icon,
    AssetType.infographic,
    AssetType.chart,
})

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Asset retrieval
# ---------------------------------------------------------------------------


def _retrieve_assets_for_plan(
    job_id: str,
    plan: list[SlidePlan],
    parsed: ParsedDeck,
) -> None:
    """Query the asset store for each slide's planned asset types.

    This is the retrieval step described in docs §9: deterministic filter
    (approved + correct slot) then vector rank on survivors.  The results are
    logged here; actual shape-tree merging of infographic fragments is a
    follow-up task (increment 4).

    The store may be empty in offline/test mode — that is fine; the composer
    falls back to template-only layouts.
    """
    store = get_store()
    slide_index = {ps.index: ps for ps in parsed.slides}

    for plan_entry in plan:
        slide = slide_index.get(plan_entry.index)
        query_text = slide.title if slide else ""
        slot = _SLIDE_TYPE_TO_SLOT.get(plan_entry.slide_type, AssetSlot.content)

        for asset_type in plan_entry.asset_types:
            if asset_type not in _LIBRARY_ASSET_TYPES:
                continue  # template/logo come from files, not the asset library

            results = store.retrieve(
                slot=slot,
                asset_type=asset_type,
                query_text=query_text,
                k=1,
            )
            if results:
                logger.info(
                    "[%s] Slide %d: retrieved %s (%s, score=%s)",
                    job_id,
                    plan_entry.index,
                    results[0].name,
                    asset_type.value,
                    "cosine",
                )
            else:
                logger.debug(
                    "[%s] Slide %d: no %s assets in store for slot=%s",
                    job_id,
                    plan_entry.index,
                    asset_type.value,
                    slot.value,
                )


# ---------------------------------------------------------------------------
# Validate gate
# ---------------------------------------------------------------------------


def _validate_gate(
    parsed: ParsedDeck,
    prs: object,
) -> tuple[bool, str, set[int], ContentDiffResult]:
    """Run all three validators against *prs*.

    Returns
    -------
    passed : bool
    fidelity_str : str
    flagged_indices : set[int]   — slide indices where issues remain
    content_result : ContentDiffResult
    """
    brand_result = lint(prs)
    content_result = diff(parsed, prs)
    layout_result = layout_check(prs)

    passed = brand_result.passed and content_result.passed and layout_result.passed
    fidelity_str = content_result.fidelity_str

    # Collect flagged slide indices from brand + layout issues.
    flagged: set[int] = set()
    for v in brand_result.violations:
        flagged.add(v.slide_index)
    for issue in layout_result.issues:
        flagged.add(issue.slide_index)

    if not passed:
        logger.info(
            "Validate gate failed — brand: %s, content: %s, layout: %s",
            brand_result.passed,
            content_result.passed,
            layout_result.passed,
        )

    return passed, fidelity_str, flagged, content_result


# ---------------------------------------------------------------------------
# Segment A — parse + plan
# ---------------------------------------------------------------------------


def run_segment_a(
    job_id: str,
    input_path: Path,
    deck_name: str,
    allow_restructure: bool,
) -> None:
    """Run the first pipeline segment: parse → analyze → plan_ready.

    Called by the job engine (background thread / inline). Updates the store
    at each step so the frontend's poll sees live progress.
    """
    try:
        # ---- parsing ----
        job_store.update(job_id, status=JobStatus.parsing)
        logger.info("[%s] Segment A: parsing %s", job_id, input_path)
        parsed = parse(input_path, deck_name)

        # ---- analyzing ----
        job_store.update(job_id, status=JobStatus.analyzing)
        logger.info("[%s] Segment A: building plan (%d slides)", job_id, len(parsed.slides))
        plan = build_plan(parsed, allow_restructure)

        # ---- persist + pause ----
        job_store.update(
            job_id,
            status=JobStatus.plan_ready,
            slide_count=len(parsed.slides),
            plan=plan,
            _parsed=parsed,  # cache for segment_b
        )
        logger.info("[%s] Segment A: plan_ready (%d plan entries)", job_id, len(plan))

    except Exception as exc:
        logger.exception("[%s] Segment A failed: %s", job_id, exc)
        job_store.update(job_id, status=JobStatus.failed, error=str(exc))


# ---------------------------------------------------------------------------
# Segment B — retrieve + compose + validate + export
# ---------------------------------------------------------------------------


def run_segment_b(job_id: str) -> None:
    """Run the second pipeline segment: retrieving → … → completed.

    Reads the ``ParsedDeck`` cached by segment_a. On validate failure, retries
    compose+validate up to ``settings.max_regenerations`` times, then completes
    as *partial success* (brandCompliancePassed=False + flagged slides). Only
    an unhandled exception transitions to ``failed``.
    """
    try:
        record = job_store.get(job_id)
        if record is None:
            logger.error("[%s] Segment B: job not found", job_id)
            return

        parsed: ParsedDeck | None = record._parsed
        if parsed is None:
            raise ValueError("ParsedDeck not cached from segment_a — cannot compose")

        t0 = time.perf_counter()

        plan = record.plan or []

        # ---- retrieving — look up assets from the library for each slide ----
        job_store.update(job_id, status=JobStatus.retrieving)
        logger.info("[%s] Segment B: retrieving assets for %d slides", job_id, len(plan))
        _retrieve_assets_for_plan(job_id, plan, parsed)

        # ---- composing ----
        job_store.update(job_id, status=JobStatus.composing)
        logger.info("[%s] Segment B: composing", job_id)
        # Load the template once; reuse across retries to avoid repeated I/O.
        from app.templates.clone_fill import load_template as _load_template
        tmpl_prs = _load_template(settings.template_pptx)
        prs, compose_overflow, infographic_indices = compose(parsed, plan, settings.assets_root, tmpl_prs)

        # ---- validating (with bounded retry) ----
        job_store.update(job_id, status=JobStatus.validating)
        gate_passed = False
        fidelity_str = ""
        flagged_indices: set[int] = set()
        content_result: ContentDiffResult | None = None
        retry_count = 0

        for attempt in range(settings.max_regenerations + 1):
            gate_passed, fidelity_str, flagged_indices, content_result = _validate_gate(parsed, prs)
            if gate_passed:
                retry_count = attempt
                break
            if attempt < settings.max_regenerations:
                logger.info(
                    "[%s] Validate gate failed (attempt %d/%d); recomposing",
                    job_id, attempt + 1, settings.max_regenerations,
                )
                # Recompose with the same plan — meaningful when the LLM Compose
                # stage arrives; deterministic compose produces the same output
                # each retry, standing up the loop structure for increment 3.
                prs, compose_overflow, infographic_indices = compose(parsed, plan, settings.assets_root, tmpl_prs)
            else:
                retry_count = attempt
                logger.info(
                    "[%s] Validate gate exhausted (%d retries); completing as partial success",
                    job_id, retry_count,
                )

        # Merge compose-time overflow flags into the validate-gate flagged set
        flagged_indices |= compose_overflow

        assert content_result is not None  # always set after the loop

        # ---- exporting ----
        job_store.update(job_id, status=JobStatus.exporting)
        logger.info("[%s] Segment B: exporting", job_id)
        pptx_path, pdf_path = export(job_id, prs)

        # ---- render per-slide preview PNGs (non-fatal if tools unavailable) ----
        input_pptx = OUT_ROOT / job_id / "input.pptx"
        orig_pngs = render_previews(job_id, input_pptx, "original")
        trans_pngs = render_previews(job_id, pptx_path, "transformed", reuse_pdf=pdf_path)

        n = len(parsed.slides)
        orig_urls = [
            f"/api/jobs/{job_id}/previews/original/slide-{i + 1}.png"
            if i < len(orig_pngs) else ""
            for i in range(n)
        ]
        # trans_pngs includes the appended closing slide (n+1 total), so use its
        # actual length — not n — to generate preview URLs for every output slide.
        trans_urls = [
            f"/api/jobs/{job_id}/previews/transformed/slide-{i + 1}.png"
            if i < len(trans_pngs) else ""
            for i in range(len(trans_pngs))
        ]

        elapsed = int(time.perf_counter() - t0)

        # ---- build slide results (one card per source slide) ----
        slides = build_slides(
            parsed,
            plan,
            content_result,
            original_preview_urls=orig_urls,
            transformed_preview_urls=trans_urls,
            flagged_indices=flagged_indices if not gate_passed else None,
            retry_count=retry_count,
            infographic_indices=infographic_indices,
        )

        # ---- append a card for the brand closing slide (always added by composer) ----
        closing_trans_url = trans_urls[n] if n < len(trans_urls) else ""
        slides.append(TransformedSlide(
            id=str(uuid.uuid4()),
            index=n,
            original_preview_url="",
            transformed_preview_url=closing_trans_url,
            content_unchanged=True,
            restructure_note="Brand closing slide (appended)",
            change_chips=["Added"],
            approval=ApprovalState.pending,
            retry_count=0,
            theme_toggleable=False,
        ))

        job_store.update(
            job_id,
            status=JobStatus.completed,
            pptx_path=pptx_path,
            pdf_path=pdf_path,
            processing_seconds=elapsed,
            slide_count=len(slides),  # n+1 (source slides + closing)
            slides=slides,
            brand_compliance_passed=gate_passed,
            content_fidelity=fidelity_str,
        )
        logger.info(
            "[%s] Segment B: completed in %ds (brand_ok=%s, fidelity=%s)",
            job_id, elapsed, gate_passed, fidelity_str,
        )

    except Exception as exc:
        logger.exception("[%s] Segment B failed: %s", job_id, exc)
        job_store.update(job_id, status=JobStatus.failed, error=str(exc))
