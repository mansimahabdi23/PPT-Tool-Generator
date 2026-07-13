"""Job-related Pydantic models — mirrors TransformJob, SlidePlan, TransformedSlide in types.ts."""


from .base import CamelModel
from .enums import ApprovalState, AssetType, JobStatus, SlideType


class SlidePlan(CamelModel):
    """Mirrors ``interface SlidePlan`` in types.ts."""

    id: str
    index: int
    slide_type: SlideType
    planned_layout: str
    asset_types: list[AssetType]
    restructure_note: str | None = None
    # Layout catalog selection — set by Analyze-and-Plan; consumed by clone-and-fill (Step 2)
    template_slide_index: int | None = None   # 1-based index into iMocha_PPT_Template_New__2026_.pptx
    layout_category: str | None = None        # LayoutCategory literal (e.g. "body-block", "cards")
    overflow_flagged: bool = False            # True when item count exceeds body-block capacity


class TransformedSlide(CamelModel):
    """Mirrors ``interface TransformedSlide`` in types.ts."""

    id: str
    index: int
    original_preview_url: str
    transformed_preview_url: str
    content_unchanged: bool
    restructure_note: str | None = None
    change_chips: list[str]
    approval: ApprovalState
    retry_count: int | None = None


class TransformJob(CamelModel):
    """Mirrors ``interface TransformJob`` in types.ts."""

    id: str
    deck_name: str
    status: JobStatus
    allow_restructure: bool
    slide_count: int
    created_at: str  # ISO-8601 string; datetime kept as str to match the TS string type
    plan: list[SlidePlan] | None = None
    slides: list[TransformedSlide] | None = None
    brand_compliance_passed: bool | None = None
    content_fidelity: str | None = None
    processing_seconds: int | None = None
