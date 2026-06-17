"""Unit tests for Pydantic models.

Checks:
- camelCase serialisation (alias round-trip)
- Enum membership exactly matches §7 of docs/architecture.md
- Optional fields default to None / non-optional lists default correctly
"""


from app.models.asset import BrandAsset, BrandAssetUpdate
from app.models.base import CamelModel
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
# Enum membership — must exactly mirror types.ts §7
# ---------------------------------------------------------------------------

class TestEnumMembers:
    def test_job_status_members(self) -> None:
        expected = {"parsing", "analyzing", "plan_ready", "retrieving", "composing",
                    "validating", "exporting", "completed", "failed"}
        assert {e.value for e in JobStatus} == expected

    def test_slide_type_members(self) -> None:
        assert {e.value for e in SlideType} == {"title", "agenda", "content", "data", "divider", "closing"}

    def test_approval_state_members(self) -> None:
        assert {e.value for e in ApprovalState} == {"pending", "approved", "regenerating", "flagged"}

    def test_asset_type_members(self) -> None:
        assert {e.value for e in AssetType} == {"template", "icon", "infographic", "logo", "chart"}

    def test_asset_status_members(self) -> None:
        assert {e.value for e in AssetStatus} == {"approved", "pending", "deprecated"}

    def test_asset_slot_members(self) -> None:
        assert {e.value for e in AssetSlot} == {"cover", "content", "divider", "closing"}


# ---------------------------------------------------------------------------
# camelCase serialisation
# ---------------------------------------------------------------------------

class TestCamelSerialisation:
    def test_camel_model_serialises_alias(self) -> None:
        """CamelModel subclass: snake_case field → camelCase JSON key."""

        class Foo(CamelModel):
            my_field: str
            another_field: int

        foo = Foo(my_field="hello", another_field=42)
        data = foo.model_dump(by_alias=True)
        assert "myField" in data
        assert "anotherField" in data
        assert "my_field" not in data

    def test_transform_job_camel_keys(self) -> None:
        job = TransformJob(
            id="j1",
            deck_name="Test.pptx",
            status=JobStatus.parsing,
            allow_restructure=False,
            slide_count=5,
            created_at="2026-06-17T00:00:00Z",
        )
        data = job.model_dump(by_alias=True)
        assert "deckName" in data
        assert "allowRestructure" in data
        assert "slideCount" in data
        assert "createdAt" in data

    def test_job_result_camel_keys(self) -> None:
        result = JobResult(
            pptx_url="https://x/a.pptx",
            pdf_url="https://x/a.pdf",
            brand_compliance_passed=True,
            content_fidelity="100%",
            processing_seconds=10,
        )
        data = result.model_dump(by_alias=True)
        assert "pptxUrl" in data
        assert "pdfUrl" in data
        assert "brandCompliancePassed" in data
        assert "contentFidelity" in data
        assert "processingSeconds" in data

    def test_brand_asset_camel_keys(self) -> None:
        asset = BrandAsset(
            id="a1",
            name="Cover",
            type=AssetType.template,
            slot=AssetSlot.cover,
            status=AssetStatus.approved,
            version="v1",
            owner="Brand",
            tags=[],
            thumbnail_url="https://x/t.png",
        )
        data = asset.model_dump(by_alias=True)
        assert "thumbnailUrl" in data
        assert "expiresAt" in data  # optional key still present (as None)

    def test_populate_by_name(self) -> None:
        """Models can also be constructed with snake_case names (useful in tests/fixtures)."""
        job = TransformJob(
            id="j2",
            deck_name="Demo.pptx",
            status=JobStatus.analyzing,
            allow_restructure=True,
            slide_count=3,
            created_at="2026-06-17T00:00:00Z",
        )
        assert job.deck_name == "Demo.pptx"


# ---------------------------------------------------------------------------
# Optional / default values
# ---------------------------------------------------------------------------

class TestOptionalFields:
    def test_transform_job_optionals_default_none(self) -> None:
        job = TransformJob(
            id="j3",
            deck_name="x.pptx",
            status=JobStatus.failed,
            allow_restructure=False,
            slide_count=0,
            created_at="2026-06-17T00:00:00Z",
        )
        assert job.plan is None
        assert job.slides is None
        assert job.brand_compliance_passed is None
        assert job.content_fidelity is None
        assert job.processing_seconds is None

    def test_slide_plan_optional_restructure_note(self) -> None:
        sp = SlidePlan(
            id="p1",
            index=1,
            slide_type=SlideType.title,
            planned_layout="Hero",
            asset_types=[],
        )
        assert sp.restructure_note is None

    def test_transformed_slide_optional_fields(self) -> None:
        ts = TransformedSlide(
            id="s1",
            index=1,
            original_preview_url="https://x/o.png",
            transformed_preview_url="https://x/t.png",
            content_unchanged=True,
            change_chips=[],
            approval=ApprovalState.pending,
        )
        assert ts.restructure_note is None
        assert ts.retry_count is None

    def test_brand_asset_optional_expires_at(self) -> None:
        asset = BrandAsset(
            id="a1",
            name="Logo",
            type=AssetType.logo,
            slot=AssetSlot.cover,
            status=AssetStatus.approved,
            version="v1",
            owner="Brand",
            tags=[],
            thumbnail_url="https://x/t.png",
        )
        assert asset.expires_at is None

    def test_brand_asset_update_all_none(self) -> None:
        upd = BrandAssetUpdate()
        assert upd.name is None
        assert upd.status is None

    def test_job_created_response(self) -> None:
        r = JobCreatedResponse(job_id="j1")
        data = r.model_dump(by_alias=True)
        assert data == {"jobId": "j1"}
