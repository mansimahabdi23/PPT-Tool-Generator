"""Typed placeholder instances used by stub routers and tests.

Mirrors the spirit of Front-End/src/lib/mockData.ts so the same logical
data flows through both sides during the stub phase.
"""

from app.models.asset import BrandAsset
from app.models.enums import (
    ApprovalState,
    AssetSlot,
    AssetStatus,
    AssetType,
    JobStatus,
    SlideType,
)
from app.models.job import SlidePlan, TransformedSlide, TransformJob
from app.models.responses import JobCreatedResponse, JobResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PH = "https://placehold.co"


def _ph(w: int, h: int, bg: str, fg: str, text: str) -> str:
    from urllib.parse import quote

    return f"{_PH}/{w}x{h}/{bg}/{fg}?text={quote(text)}&font=poppins"


# ---------------------------------------------------------------------------
# SlidePlan[]
# ---------------------------------------------------------------------------

STUB_PLAN: list[SlidePlan] = [
    SlidePlan(
        id="p1",
        index=1,
        slide_type=SlideType.title,
        planned_layout="Hero Title + Subtitle",
        asset_types=[AssetType.template, AssetType.logo],
    ),
    SlidePlan(
        id="p2",
        index=2,
        slide_type=SlideType.agenda,
        planned_layout="Numbered Agenda",
        asset_types=[AssetType.icon],
    ),
    SlidePlan(
        id="p3",
        index=3,
        slide_type=SlideType.content,
        planned_layout="Two-column with icons",
        asset_types=[AssetType.icon, AssetType.infographic],
    ),
    SlidePlan(
        id="p4",
        index=4,
        slide_type=SlideType.data,
        planned_layout="Stat callout grid",
        asset_types=[AssetType.chart, AssetType.infographic],
        restructure_note="Merged from slides 4–5",
    ),
    SlidePlan(
        id="p5",
        index=5,
        slide_type=SlideType.content,
        planned_layout="Quote card",
        asset_types=[AssetType.template],
    ),
    SlidePlan(
        id="p6",
        index=6,
        slide_type=SlideType.data,
        planned_layout="Bar chart with insights",
        asset_types=[AssetType.chart],
    ),
    SlidePlan(
        id="p7",
        index=7,
        slide_type=SlideType.divider,
        planned_layout="Section divider",
        asset_types=[AssetType.template],
    ),
    SlidePlan(
        id="p8",
        index=8,
        slide_type=SlideType.closing,
        planned_layout="Thank you / contact",
        asset_types=[AssetType.logo, AssetType.icon],
    ),
]


# ---------------------------------------------------------------------------
# TransformedSlide[]
# ---------------------------------------------------------------------------

def _make_slide(
    i: int,
    chips: list[str],
    restructure_note: str | None = None,
) -> TransformedSlide:
    return TransformedSlide(
        id=f"s{i}",
        index=i,
        original_preview_url=_ph(640, 360, "e5e7eb", "6b7280", f"Original Slide {i}"),
        transformed_preview_url=_ph(640, 360, "ff4a00", "ffffff", f"iMocha Slide {i}"),
        content_unchanged=True,
        change_chips=chips,
        approval=ApprovalState.pending,
        restructure_note=restructure_note,
    )


STUB_SLIDES: list[TransformedSlide] = [
    _make_slide(1, ["Brand colors applied", "Display type added"]),
    _make_slide(2, ["Layout improved", "Icons added"]),
    _make_slide(3, ["Brand colors applied", "Icon added"]),
    _make_slide(4, ["Merged content", "Chart redesigned"], restructure_note="Merged from slides 4–5"),
    _make_slide(5, ["Typography refined"]),
    _make_slide(6, ["Chart redesigned", "Insights highlighted"]),
    _make_slide(7, ["Divider styled"]),
    _make_slide(8, ["Brand colors applied", "Contact block added"]),
]


# ---------------------------------------------------------------------------
# TransformJob (single + history list)
# ---------------------------------------------------------------------------

STUB_JOB_ID = "job_stub_001"

STUB_JOB: TransformJob = TransformJob(
    id=STUB_JOB_ID,
    deck_name="Q3 Sales Pitch.pptx",
    status=JobStatus.completed,
    allow_restructure=True,
    slide_count=8,
    created_at="2026-06-17T10:00:00Z",
    plan=STUB_PLAN,
    slides=STUB_SLIDES,
    brand_compliance_passed=True,
    content_fidelity="100% of claims preserved",
    processing_seconds=42,
)

STUB_JOB_HISTORY: list[TransformJob] = [
    STUB_JOB,
    TransformJob(
        id="job_stub_002",
        deck_name="Enterprise Onboarding.pptx",
        status=JobStatus.completed,
        allow_restructure=False,
        slide_count=18,
        created_at="2026-06-07T14:10:00Z",
        brand_compliance_passed=True,
        content_fidelity="100% of claims preserved",
        processing_seconds=62,
    ),
    TransformJob(
        id="job_stub_003",
        deck_name="Investor Update.pptx",
        status=JobStatus.failed,
        allow_restructure=False,
        slide_count=0,
        created_at="2026-06-03T16:45:00Z",
    ),
]


# ---------------------------------------------------------------------------
# JobCreatedResponse
# ---------------------------------------------------------------------------

STUB_JOB_CREATED = JobCreatedResponse(job_id=STUB_JOB_ID)


# ---------------------------------------------------------------------------
# JobResult
# ---------------------------------------------------------------------------

STUB_JOB_RESULT = JobResult(
    pptx_url=f"https://storage.example.com/{STUB_JOB_ID}.pptx",
    pdf_url=f"https://storage.example.com/{STUB_JOB_ID}.pdf",
    brand_compliance_passed=True,
    content_fidelity="100% of claims preserved",
    processing_seconds=42,
)


# ---------------------------------------------------------------------------
# BrandAsset[]
# ---------------------------------------------------------------------------

STUB_ASSETS: list[BrandAsset] = [
    BrandAsset(
        id="a1",
        name="iMocha Cover Template",
        type=AssetType.template,
        slot=AssetSlot.cover,
        status=AssetStatus.approved,
        version="v3.2",
        owner="Brand Team",
        tags=["cover", "hero"],
        thumbnail_url=_ph(240, 160, "ff4a00", "ffffff", "Cover"),
    ),
    BrandAsset(
        id="a2",
        name="iMocha Logo (Light)",
        type=AssetType.logo,
        slot=AssetSlot.cover,
        status=AssetStatus.approved,
        version="v2.0",
        owner="Brand Team",
        tags=["logo"],
        thumbnail_url=_ph(240, 160, "111827", "ff4a00", "Logo"),
    ),
    BrandAsset(
        id="a3",
        name="Skill Assessment Icon Set",
        type=AssetType.icon,
        slot=AssetSlot.content,
        status=AssetStatus.approved,
        version="v1.4",
        owner="Design",
        tags=["icons", "skills"],
        thumbnail_url=_ph(240, 160, "ede9fe", "5b21b6", "Icons"),
    ),
    BrandAsset(
        id="a4",
        name="Talent Funnel Infographic",
        type=AssetType.infographic,
        slot=AssetSlot.content,
        status=AssetStatus.approved,
        version="v1.0",
        owner="Design",
        tags=["funnel"],
        thumbnail_url=_ph(240, 160, "481aec", "ffffff", "Funnel"),
    ),
    BrandAsset(
        id="a5",
        name="ROI Chart Template",
        type=AssetType.chart,
        slot=AssetSlot.content,
        status=AssetStatus.pending,
        version="v0.9",
        owner="Marketing",
        tags=["roi", "chart"],
        thumbnail_url=_ph(240, 160, "7c3aed", "ffffff", "Chart"),
    ),
    BrandAsset(
        id="a6",
        name="Section Divider — Orange",
        type=AssetType.template,
        slot=AssetSlot.divider,
        status=AssetStatus.approved,
        version="v2.1",
        owner="Brand Team",
        tags=["divider"],
        thumbnail_url=_ph(240, 160, "fd5b0e", "ffffff", "Divider"),
    ),
    BrandAsset(
        id="a7",
        name="Closing Thank You",
        type=AssetType.template,
        slot=AssetSlot.closing,
        status=AssetStatus.approved,
        version="v1.8",
        owner="Brand Team",
        tags=["closing"],
        thumbnail_url=_ph(240, 160, "111827", "ffffff", "Thanks"),
    ),
    BrandAsset(
        id="a8",
        name="Legacy Cover (2022)",
        type=AssetType.template,
        slot=AssetSlot.cover,
        status=AssetStatus.deprecated,
        version="v1.0",
        owner="Brand Team",
        expires_at="2024-01-01",
        tags=["legacy"],
        thumbnail_url=_ph(240, 160, "9ca3af", "ffffff", "Legacy"),
    ),
]
