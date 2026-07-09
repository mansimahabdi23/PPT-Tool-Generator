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
