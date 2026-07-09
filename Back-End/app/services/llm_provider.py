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
import uuid
from typing import Any, Protocol, runtime_checkable

from app.models.enums import AssetType, SlideType
from app.models.job import SlidePlan
from app.services.parser import ParsedDeck

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
        plans: list[SlidePlan] = []
        for i, slide in enumerate(parsed.slides):
            slide_type = slide.slide_type
            note: str | None = None
            if allow_restructure:
                note = (
                    "Restructuring enabled — the Analyze & Plan LLM may propose "
                    "reordering or merging this slide."
                )
            plans.append(SlidePlan(
                id=str(uuid.uuid4()),
                index=i,
                slide_type=slide_type,
                planned_layout=_LAYOUT_MAP.get(slide_type, "Standard content layout"),
                asset_types=_ASSET_TYPE_MAP.get(slide_type, [AssetType.template]),
                restructure_note=note,
            ))
        return plans


# ---------------------------------------------------------------------------
# Azure OpenAI — real provider, activated by config
# ---------------------------------------------------------------------------

# Strict JSON schema for one SlidePlan entry.
# OpenAI structured outputs require: all properties in "required",
# additionalProperties=false, nullable via anyOf.
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
    },
    "required": ["id", "index", "slideType", "plannedLayout", "assetTypes", "restructureNote"],
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
