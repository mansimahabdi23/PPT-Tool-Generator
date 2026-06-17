"""Contract test: validates the live OpenAPI schema against docs/architecture.md §8.

Checks that every endpoint specified in the API contract exists in the schema with the
correct HTTP method and path, and that key response-model fields appear in the component
schemas — ensuring the Pydantic models haven't drifted from the TypeScript types.
"""

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# §8 endpoint inventory: (method, path-as-in-openapi)
# ---------------------------------------------------------------------------

REQUIRED_ENDPOINTS: list[tuple[str, str]] = [
    ("post", "/api/jobs"),
    ("get", "/api/jobs"),
    ("get", "/api/jobs/{job_id}"),
    ("get", "/api/jobs/{job_id}/plan"),
    ("post", "/api/jobs/{job_id}/plan/approve"),
    ("post", "/api/jobs/{job_id}/slides/{slide_id}/regenerate"),
    ("get", "/api/jobs/{job_id}/result"),
    ("get", "/api/assets"),
    ("post", "/api/assets"),
    ("patch", "/api/assets/{asset_id}"),
]

# Required camelCase properties per response schema (a subset is enough —
# if these survive the round-trip the alias_generator is working).
SCHEMA_FIELD_CHECKS: dict[str, list[str]] = {
    "TransformJob": ["id", "deckName", "status", "allowRestructure", "slideCount", "createdAt"],
    "SlidePlan": ["id", "index", "slideType", "plannedLayout", "assetTypes"],
    "TransformedSlide": [
        "id", "index", "originalPreviewUrl", "transformedPreviewUrl",
        "contentUnchanged", "changeChips", "approval",
    ],
    "BrandAsset": ["id", "name", "type", "slot", "status", "version", "owner", "tags", "thumbnailUrl"],
    "JobCreatedResponse": ["jobId"],
    "JobResult": ["pptxUrl", "pdfUrl", "brandCompliancePassed", "contentFidelity", "processingSeconds"],
}


@pytest.fixture(scope="module")
def schema(client: TestClient) -> dict:  # type: ignore[type-arg]
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


class TestEndpointCoverage:
    """Every endpoint from docs/architecture.md §8 must appear in the schema."""

    def test_all_endpoints_present(self, schema: dict) -> None:  # type: ignore[type-arg]
        paths: dict = schema.get("paths", {})
        missing = []
        for method, path in REQUIRED_ENDPOINTS:
            if path not in paths or method not in paths[path]:
                missing.append(f"{method.upper()} {path}")
        assert not missing, "Missing endpoints in OpenAPI schema:\n" + "\n".join(missing)

    @pytest.mark.parametrize("method,path", REQUIRED_ENDPOINTS)
    def test_endpoint_has_response(self, schema: dict, method: str, path: str) -> None:  # type: ignore[type-arg]
        """Each endpoint must declare at least one response code."""
        op = schema["paths"][path][method]
        assert "responses" in op, f"{method.upper()} {path} has no responses"
        assert op["responses"], f"{method.upper()} {path} responses is empty"


class TestResponseSchemas:
    """Key camelCase fields must appear in the component schemas."""

    @pytest.mark.parametrize("model_name,fields", SCHEMA_FIELD_CHECKS.items())
    def test_model_has_required_fields(
        self,
        schema: dict,  # type: ignore[type-arg]
        model_name: str,
        fields: list[str],
    ) -> None:
        components = schema.get("components", {}).get("schemas", {})
        assert model_name in components, f"Schema component '{model_name}' not found"
        props = components[model_name].get("properties", {})
        missing = [f for f in fields if f not in props]
        assert not missing, (
            f"'{model_name}' missing properties: {missing}\n"
            f"Actual properties: {sorted(props.keys())}"
        )

    def test_job_status_enum_values(self, schema: dict) -> None:  # type: ignore[type-arg]
        """JobStatus enum values in the schema must exactly match the TS contract (§7)."""
        expected = {"parsing", "analyzing", "plan_ready", "retrieving", "composing",
                    "validating", "exporting", "completed", "failed"}
        components = schema["components"]["schemas"]
        status_schema = components.get("JobStatus", {})
        actual = set(status_schema.get("enum", []))
        assert actual == expected, f"JobStatus enum mismatch.\nExpected: {sorted(expected)}\nGot: {sorted(actual)}"

    def test_approval_state_enum_values(self, schema: dict) -> None:  # type: ignore[type-arg]
        expected = {"pending", "approved", "regenerating", "flagged"}
        components = schema["components"]["schemas"]
        actual = set(components.get("ApprovalState", {}).get("enum", []))
        assert actual == expected

    def test_asset_type_enum_values(self, schema: dict) -> None:  # type: ignore[type-arg]
        expected = {"template", "icon", "infographic", "logo", "chart"}
        components = schema["components"]["schemas"]
        actual = set(components.get("AssetType", {}).get("enum", []))
        assert actual == expected


class TestApproveReturns202:
    """POST /plan/approve must be declared as 202 Accepted."""

    def test_approve_plan_status_code(self, schema: dict) -> None:  # type: ignore[type-arg]
        op = schema["paths"]["/api/jobs/{job_id}/plan/approve"]["post"]
        assert "202" in op["responses"], (
            "POST /plan/approve must declare 202 response; got: " + str(list(op["responses"].keys()))
        )
