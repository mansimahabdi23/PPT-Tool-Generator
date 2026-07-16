"""String enums mirroring the TypeScript union types in Front-End/src/types.ts (§7)."""

from enum import StrEnum


class JobStatus(StrEnum):
    parsing = "parsing"
    analyzing = "analyzing"
    plan_ready = "plan_ready"
    retrieving = "retrieving"
    composing = "composing"
    validating = "validating"
    exporting = "exporting"
    completed = "completed"
    failed = "failed"
    purged = "purged"


class SlideType(StrEnum):
    title = "title"  # type: ignore[assignment]  # conflicts with str.title() method
    agenda = "agenda"
    content = "content"
    data = "data"
    divider = "divider"
    closing = "closing"


class ApprovalState(StrEnum):
    pending = "pending"
    approved = "approved"
    regenerating = "regenerating"
    flagged = "flagged"


class AssetType(StrEnum):
    template = "template"
    icon = "icon"
    infographic = "infographic"
    logo = "logo"
    chart = "chart"


class SlideTheme(StrEnum):
    light = "light"
    dark = "dark"


class AssetStatus(StrEnum):
    approved = "approved"
    pending = "pending"
    deprecated = "deprecated"


class AssetSlot(StrEnum):
    """Slot values for BrandAsset (not a standalone TS type but part of the BrandAsset interface)."""

    cover = "cover"
    content = "content"
    divider = "divider"
    closing = "closing"


class FragmentIntent(StrEnum):
    """Structural intent of an infographic fragment.

    Used as a hard filter in retrieve() — a sequential-process fragment must
    not be selected for a slide whose content is unordered parallel features,
    and vice versa.  Icons carry intent=None (unused).
    """

    parallel_features  = "parallel-features"   # unordered, equal-weight features/capabilities
    sequential_process = "sequential-process"   # ordered steps, workflow, progression
    timeline           = "timeline"             # chronological milestones on an axis
    hierarchy          = "hierarchy"            # tree / pyramid / org structure
    data_chart         = "data-chart"           # charts, KPIs, metrics, dashboards
    comparison         = "comparison"           # side-by-side A vs B (reserved for future)
    single_stat        = "single-stat"          # one metric, one person, one callout
    roadmap            = "roadmap"              # roadmap grid (time × workstream)
    geographic         = "geographic"           # maps, regional panels
