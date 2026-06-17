"""Route tests for /api/jobs endpoints.

Each test verifies:
  - correct HTTP status code
  - response body is camelCase JSON matching the declared response_model
"""

import io

from fastapi.testclient import TestClient


class TestCreateJob:
    def test_returns_201_with_job_id(self, client: TestClient) -> None:
        fake_file = io.BytesIO(b"PK fake pptx content")
        response = client.post(
            "/api/jobs",
            files={"file": ("deck.pptx", fake_file, "application/vnd.ms-powerpoint")},
            data={"allow_restructure": "false"},
        )
        assert response.status_code == 201
        body = response.json()
        assert "jobId" in body
        assert isinstance(body["jobId"], str)


class TestListJobs:
    def test_returns_200_list(self, client: TestClient) -> None:
        response = client.get("/api/jobs")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_list_items_are_camel_case(self, client: TestClient) -> None:
        response = client.get("/api/jobs")
        job = response.json()[0]
        assert "deckName" in job
        assert "slideCount" in job
        assert "allowRestructure" in job
        assert "createdAt" in job
        assert "status" in job

    def test_accepts_paging_params(self, client: TestClient) -> None:
        response = client.get("/api/jobs?page=2&page_size=5")
        assert response.status_code == 200


class TestGetJob:
    def test_returns_200_transform_job(self, client: TestClient) -> None:
        response = client.get("/api/jobs/job_stub_001")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "job_stub_001"
        assert "deckName" in body
        assert "status" in body

    def test_completed_job_has_slides_and_plan(self, client: TestClient) -> None:
        response = client.get("/api/jobs/job_stub_001")
        body = response.json()
        assert body["status"] == "completed"
        assert isinstance(body["plan"], list)
        assert len(body["plan"]) > 0
        assert isinstance(body["slides"], list)
        assert len(body["slides"]) > 0

    def test_slides_are_camel_case(self, client: TestClient) -> None:
        body = client.get("/api/jobs/job_stub_001").json()
        slide = body["slides"][0]
        assert "originalPreviewUrl" in slide
        assert "transformedPreviewUrl" in slide
        assert "contentUnchanged" in slide
        assert "changeChips" in slide
        assert "approval" in slide

    def test_plan_items_are_camel_case(self, client: TestClient) -> None:
        body = client.get("/api/jobs/job_stub_001").json()
        plan_item = body["plan"][0]
        assert "slideType" in plan_item
        assert "plannedLayout" in plan_item
        assert "assetTypes" in plan_item


class TestGetPlan:
    def test_returns_200_list_of_slide_plans(self, client: TestClient) -> None:
        response = client.get("/api/jobs/job_stub_001/plan")
        assert response.status_code == 200
        plan = response.json()
        assert isinstance(plan, list)
        assert len(plan) == 8  # matches STUB_PLAN

    def test_plan_item_fields(self, client: TestClient) -> None:
        plan = client.get("/api/jobs/job_stub_001/plan").json()
        item = plan[0]
        assert "id" in item
        assert "index" in item
        assert "slideType" in item
        assert "plannedLayout" in item
        assert "assetTypes" in item


class TestApprovePlan:
    def test_returns_202_with_transform_job(self, client: TestClient) -> None:
        response = client.post("/api/jobs/job_stub_001/plan/approve")
        assert response.status_code == 202
        body = response.json()
        assert "id" in body
        assert "status" in body
        assert "deckName" in body


class TestRegenerateSlide:
    def test_returns_200_transformed_slide(self, client: TestClient) -> None:
        response = client.post("/api/jobs/job_stub_001/slides/s1/regenerate")
        assert response.status_code == 200
        body = response.json()
        assert "id" in body
        assert "originalPreviewUrl" in body
        assert "transformedPreviewUrl" in body
        assert "approval" in body


class TestGetResult:
    def test_returns_200_job_result(self, client: TestClient) -> None:
        response = client.get("/api/jobs/job_stub_001/result")
        assert response.status_code == 200
        body = response.json()
        assert "pptxUrl" in body
        assert "pdfUrl" in body
        assert "brandCompliancePassed" in body
        assert "contentFidelity" in body
        assert "processingSeconds" in body

    def test_result_urls_are_strings(self, client: TestClient) -> None:
        body = client.get("/api/jobs/job_stub_001/result").json()
        assert isinstance(body["pptxUrl"], str)
        assert isinstance(body["pdfUrl"], str)
