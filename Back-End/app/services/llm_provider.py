"""LLM provider interface — Analyze & Plan agent.

Two implementations behind a single seam:

Provider            | When active                          | Notes
--------------------|--------------------------------------|----------------------------
StubProvider        | default (LLM_PROVIDER="stub")        | deterministic, offline, testable
AzureOpenAIProvider | LLM_PROVIDER="azure_openai"          | Azure OpenAI chat completions
                    | + AZURE_OPENAI_ENDPOINT configured   |

Callers always go through get_provider() so the implementation is
swappable without changing any call site.  Prod activation:
  LLM_PROVIDER=azure_openai
  AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
  AZURE_OPENAI_API_KEY=<key>
  AZURE_OPENAI_DEPLOYMENT=<deployment-name>   (default: gpt-4o)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Protocol, runtime_checkable

from app.models.enums import AssetType, FragmentIntent, SlideType
from app.models.job import SlidePlan
from app.services.parser import ParsedDeck, ParsedSlide
from app.templates.layout_catalog import SHORT_LABEL_MAX_WORDS, select_catalog_entry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """One-method interface for the Analyze & Plan step."""

    def analyze_deck(
        self,
        parsed: ParsedDeck,
        allow_restructure: bool,
    ) -> list[SlidePlan]:
        """Classify each slide and return a SlidePlan list (one per slide)."""
        ...


# ---------------------------------------------------------------------------
# Stub — deterministic, offline, testable
# ---------------------------------------------------------------------------

def _apply_catalog(
    plan: SlidePlan,
    slide: ParsedSlide,
    is_first: bool,
    is_last: bool,
) -> SlidePlan:
    """Enrich *plan* with deterministic catalog layout selection.

    Sets template_slide_index, layout_category, overflow_flagged, and updates
    planned_layout to a human-readable catalog description so the Plan review
    screen shows the chosen template slide.
    """
    entry, overflow = select_catalog_entry(slide, is_first, is_last)
    # Show item capacity only for cards (e.g. "cards/3 items"); other categories are unambiguous
    if entry.category == "cards" and entry.max_items:
        layout_str = f"cards/{entry.max_items} items → template slide {entry.template_slide_index}"
    else:
        layout_str = f"{entry.category} → template slide {entry.template_slide_index}"
    return plan.model_copy(update={
        "planned_layout": layout_str,
        "template_slide_index": entry.template_slide_index,
        "layout_category": entry.category,
        "overflow_flagged": overflow,
    })


# ---------------------------------------------------------------------------
# Stub intent classifier — keyword heuristic, no LLM.
#
# Design rules:
#   · Title signals are checked first and carry more weight than bullets —
#     a title describes the slide's PURPOSE; bullets are supporting detail.
#   · data-chart uses TWO separate vocabularies: a broader one for titles
#     (where "data" is a strong signal: "Data Analytics Dashboard") and a
#     narrower one for bullets (where "data", "growth", "score", "rate" appear
#     in ordinary business prose and cause false positives).
#   · parallel-features is the catch-all for short labels with no stronger
#     signal — it fires last, never before a more specific classification.
#   · The real AzureOpenAIProvider uses LLM judgment instead of these keywords.
# ---------------------------------------------------------------------------

_SEQUENTIAL_WORDS = frozenset({
    "step", "steps", "stage", "stages", "phase", "phases",
    "process", "flow", "journey", "workflow", "progression",
    "sequence", "procedure",
})

# Chart-specific; "data" is safe here — a title like "Data Analytics Overview"
# clearly signals a data slide.
_DATA_WORDS_TITLE = frozenset({
    "chart", "charts", "metric", "metrics", "kpi", "kpis",
    "analytics", "dashboard", "statistics", "percentage",
    "donut", "pie", "gauge", "data",
})

# Bullets-only: deliberately excludes "data", "growth", "score", "rate",
# "revenue", "trends", "figures" — all appear in normal business prose and
# produce false-positive data-chart classifications on informational slides.
_DATA_WORDS_BULLETS = frozenset({
    "chart", "charts", "metric", "metrics", "kpi", "kpis",
    "analytics", "dashboard", "statistics", "percentage",
    "donut", "pie", "gauge",
})

_HIERARCHY_WORDS = frozenset({
    "hierarchy", "pyramid", "taxonomy", "levels", "tier", "tiers",
    "classification", "organization", "org",
})
_TIMELINE_WORDS = frozenset({"timeline", "milestone", "milestones"})
_ROADMAP_WORDS  = frozenset({"roadmap", "quarters"})


def _classify_intent_stub(slide: ParsedSlide) -> FragmentIntent | None:
    """Deterministic keyword-heuristic intent for offline StubProvider.

    Returns None when no signal is strong enough — the slide goes to body-block.
    Only called for non-cover/non-closing content slides.

    Title words are checked with a broader vocabulary; bullet words with a
    narrower one.  This prevents common business prose ("data across systems",
    "revenue growth") from triggering data-chart on informational slides.
    """
    items = slide.body_items or []
    if not items:
        return None

    title_words  = set(re.findall(r"\w+", (slide.title or "").lower()))
    bullet_words = set(re.findall(r"\w+", " ".join(items).lower()))
    all_words    = title_words | bullet_words

    # data-chart: title-weighted — check title with broader set, bullets with narrow set
    if (title_words & _DATA_WORDS_TITLE) or (bullet_words & _DATA_WORDS_BULLETS):
        return FragmentIntent.data_chart
    if all_words & _ROADMAP_WORDS:
        return FragmentIntent.roadmap
    if all_words & _TIMELINE_WORDS:
        return FragmentIntent.timeline
    if all_words & _HIERARCHY_WORDS:
        return FragmentIntent.hierarchy
    if all_words & _SEQUENTIAL_WORDS:
        return FragmentIntent.sequential_process
    # Fallback: all short labels with no stronger signal → unordered parallel features
    if all(len(item.split()) <= SHORT_LABEL_MAX_WORDS for item in items):
        return FragmentIntent.parallel_features
    return None


_LAYOUT_MAP: dict[SlideType, str] = {
    SlideType.title:   "Full-bleed cover with title, subtitle, and logo",
    SlideType.agenda:  "Numbered agenda list with section highlights",
    SlideType.content: "Two-column or single-column content with icon accents",
    SlideType.data:    "Chart or data table with supporting callout text",
    SlideType.divider: "Section divider with gradient background and section title",
    SlideType.closing: "Thank-you slide with CTA, logo, and contact details",
}

_ASSET_TYPE_MAP: dict[SlideType, list[AssetType]] = {
    SlideType.title:   [AssetType.logo, AssetType.template],
    SlideType.agenda:  [AssetType.icon, AssetType.template],
    SlideType.content: [AssetType.icon, AssetType.infographic],
    SlideType.data:    [AssetType.chart, AssetType.template],
    SlideType.divider: [AssetType.template],
    SlideType.closing: [AssetType.logo, AssetType.template],
}


class StubProvider:
    """Deterministic Analyze & Plan stand-in — no LLM calls.

    Produces one SlidePlan per slide using the parser's slide-type heuristic
    and fixed layout/asset mappings.  Used as the default offline/test provider.
    The real AzureOpenAIProvider is a drop-in replacement at runtime.
    """

    def analyze_deck(
        self,
        parsed: ParsedDeck,
        allow_restructure: bool,
    ) -> list[SlidePlan]:
        last = len(parsed.slides) - 1
        plans: list[SlidePlan] = []
        for i, slide in enumerate(parsed.slides):
            slide_type = slide.slide_type
            note: str | None = None
            if allow_restructure:
                note = (
                    "Restructuring enabled — the Analyze & Plan LLM may propose "
                    "reordering or merging this slide."
                )
            plan = SlidePlan(
                id=str(uuid.uuid4()),
                index=i,
                slide_type=slide_type,
                planned_layout=_LAYOUT_MAP.get(slide_type, "Standard content layout"),
                asset_types=_ASSET_TYPE_MAP.get(slide_type, [AssetType.template]),
                restructure_note=note,
            )
            plan = _apply_catalog(plan, slide, is_first=(i == 0), is_last=(i == last))
            # Classify infographic intent for content-type slides (stub heuristic).
            # Cover and closing do not receive intent; body-block is their path.
            if plan.layout_category not in ("cover", "closing"):
                intent = _classify_intent_stub(slide)
                if intent is not None:
                    plan = plan.model_copy(update={"required_intent": intent})
            plans.append(plan)
        return plans


# ---------------------------------------------------------------------------
# Azure OpenAI — real provider, activated by config
# ---------------------------------------------------------------------------

# Strict JSON schema for one SlidePlan entry.
# OpenAI structured outputs require: all properties in "required",
# additionalProperties=false, nullable via anyOf.
_INTENT_ENUM = [
    "parallel-features", "sequential-process", "timeline", "hierarchy",
    "data-chart", "comparison", "single-stat", "roadmap", "geographic",
]

_SLIDE_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id":              {"type": "string"},
        "index":           {"type": "integer"},
        "slideType":       {
            "type": "string",
            "enum": ["title", "agenda", "content", "data", "divider", "closing"],
        },
        "plannedLayout":   {"type": "string"},
        "assetTypes":      {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["template", "icon", "infographic", "logo", "chart"],
            },
        },
        "restructureNote": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "requiredIntent":  {
            "anyOf": [
                {"type": "string", "enum": _INTENT_ENUM},
                {"type": "null"},
            ],
        },
    },
    "required": [
        "id", "index", "slideType", "plannedLayout",
        "assetTypes", "restructureNote", "requiredIntent",
    ],
    "additionalProperties": False,
}

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": _SLIDE_PLAN_SCHEMA,
        },
    },
    "required": ["slides"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """\
You are the iMocha Analyze & Plan agent. Read the parsed PowerPoint presentation \
and produce a structured transformation plan — exactly one SlidePlan per input slide, \
in index order.

Slide types:
- title   : Opening cover (deck/company title, often a subtitle or tagline)
- agenda  : Table of contents or section roadmap
- content : Informational slide with bullets, paragraphs, or supporting visuals
- data    : Slide dominated by a chart, table, or statistics
- divider : Section separator / transition slide (minimal text)
- closing : Thank-you, contact, or call-to-action

Asset types (choose the most relevant; always include "template"):
- template   : base iMocha slide template (always)
- icon       : small visual accent for bullets or features
- infographic: multi-step or flow diagram
- logo       : iMocha logo (always on title and closing slides)
- chart      : bar/pie/line chart (for data slides)

plannedLayout: 10–25-word human-readable description of the target iMocha layout \
(column structure, accent elements, visual hierarchy).

restructureNote: null when allow_restructure is false. When true, optionally suggest \
reordering or merging with adjacent slides for better narrative flow — or null if \
no change is needed.

requiredIntent: Classify the STRUCTURAL INTENT of each content slide's bullet items. \
This is a HARD filter — only infographic fragments with a matching intent will be \
considered. Use exactly one of the values below, or null if none clearly applies \
(the slide will then render as body-block text):

- "parallel-features"  : Unordered, equal-weight items — capabilities, features, benefits.
                         Example: "AI Skills Engine | Conversational Assistant | Job Profile Creator"
- "sequential-process" : Ordered steps, stages, or workflow phases that must be read in sequence.
                         Example: "Step 1: Assess → Step 2: Gap-analyse → Step 3: Upskill"
- "timeline"           : Chronological milestones on a time axis (dates, quarters, years).
- "hierarchy"          : Tree, pyramid, or org structure with clear parent→child levels.
- "data-chart"         : Slide content is metrics, KPIs, percentages, or chart data.
- "comparison"         : Explicit side-by-side A vs B contrast.
- "single-stat"        : One key number, person, or callout dominates the slide.
- "roadmap"            : Roadmap grid — time (quarters/months) × workstream rows.
- "geographic"         : Regional or map-based content.

Rules:
- Return null for title, agenda, divider, and closing slides (they never use infographics).
- Return null when the bullets are full sentences (long paragraphs) — those render as body-block.
- Choose the STRONGEST signal. If bullets are short labels with no sequential keywords, \
  prefer "parallel-features" over null.

Return JSON matching the schema exactly. Use a fresh UUID for each id field.\
"""


def _serialize_deck(parsed: ParsedDeck, allow_restructure: bool) -> str:
    """Compact text representation of the parsed deck for the LLM prompt."""
    lines: list[str] = [
        f"Deck: {parsed.name}",
        f"Slides: {parsed.slide_count}",
        f"allow_restructure: {allow_restructure}",
        "",
    ]
    for slide in parsed.slides:
        lines.append(f"=== Slide {slide.index + 1} (index {slide.index}) ===")
        lines.append(f"Parser heuristic type: {slide.slide_type.value}")
        if slide.title:
            lines.append(f"Title: {slide.title!r}")
        if slide.body_items:
            lines.append(f"Bullets ({len(slide.body_items)}):")
            for b in slide.body_items[:8]:   # cap to stay within token budget
                lines.append(f"  • {b[:120]}")
        if slide.claims:
            claim_texts = [c.text for c in slide.claims[:5]]
            lines.append(f"Key claims: {', '.join(claim_texts)}")
        lines.append("")
    return "\n".join(lines)


class AzureOpenAIProvider:
    """Real Analyze & Plan agent backed by Azure OpenAI chat completions.

    Uses structured outputs (json_schema response_format) so the model is
    constrained to return valid SlidePlan JSON.  If the model returns fewer
    entries than slides, or an entry fails validation, the StubProvider fills
    the gap — so this never raises due to a bad LLM response.

    API errors (network, auth, quota) propagate to the caller (pipeline
    segment_a catches them and marks the job failed).
    """

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    def analyze_deck(
        self,
        parsed: ParsedDeck,
        allow_restructure: bool,
    ) -> list[SlidePlan]:
        user_content = _serialize_deck(parsed, allow_restructure)
        logger.info(
            "AzureOpenAIProvider.analyze_deck: %d slides via deployment=%s",
            len(parsed.slides),
            self._deployment,
        )

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name":   "slide_plans",
                    "strict": True,
                    "schema": _RESPONSE_SCHEMA,
                },
            },
            temperature=0,
        )

        content = response.choices[0].message.content
        raw_plans: list[dict[str, Any]] = json.loads(content)["slides"]

        if len(raw_plans) != len(parsed.slides):
            logger.warning(
                "AzureOpenAI returned %d plans for %d slides; will pad with stub",
                len(raw_plans),
                len(parsed.slides),
            )

        # Build a stub fallback keyed by index for gap-filling.
        stub_by_index = {
            p.index: p
            for p in StubProvider().analyze_deck(parsed, allow_restructure)
        }

        last = len(parsed.slides) - 1
        plans: list[SlidePlan] = []
        for i, slide in enumerate(parsed.slides):
            if i < len(raw_plans):
                entry = raw_plans[i]
                try:
                    plan = SlidePlan(
                        id=entry.get("id") or str(uuid.uuid4()),
                        index=slide.index,
                        slide_type=SlideType(entry["slideType"]),
                        planned_layout=entry["plannedLayout"],
                        asset_types=[AssetType(a) for a in entry.get("assetTypes", [])],
                        restructure_note=entry.get("restructureNote"),
                    )
                    plan = _apply_catalog(plan, slide, is_first=(i == 0), is_last=(i == last))
                    raw_intent = entry.get("requiredIntent")
                    if raw_intent is not None:
                        try:
                            plan = plan.model_copy(
                                update={"required_intent": FragmentIntent(raw_intent)}
                            )
                        except ValueError:
                            logger.warning(
                                "Slide %d: unknown requiredIntent %r from LLM — ignoring",
                                i, raw_intent,
                            )
                    plans.append(plan)
                except (KeyError, ValueError) as exc:
                    logger.warning(
                        "Bad plan entry for slide %d (%s) — using stub", i, exc
                    )
                    plans.append(stub_by_index[i])
            else:
                plans.append(stub_by_index[i])

        return plans


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_provider: LLMProvider | None = None


def init_provider(provider: LLMProvider) -> None:
    """Set the active provider.  Called once from app lifespan."""
    global _provider
    _provider = provider


def get_provider() -> LLMProvider:
    """Return the active LLMProvider.  Raises RuntimeError if not initialised."""
    if _provider is None:
        raise RuntimeError(
            "LLMProvider not initialised — call init_provider() in app lifespan."
        )
    return _provider
