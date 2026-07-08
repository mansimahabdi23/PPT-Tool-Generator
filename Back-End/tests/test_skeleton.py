"""Integration test: walking skeleton end-to-end roundtrip.

Upload the committed sample PPTX → assert job completes → assert PPTX download works.
The output PPTX must be openable by python-pptx with at least one slide.

Run from Back-End/:
    pytest -q tests/test_skeleton.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation

from app.main import app

# The committed sample deck — a valid 6-slide branded PPTX
SAMPLE_PPTX = Path(__file__).parent.parent / "out" / "samples_imocha_template.pptx"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def upload_sample(client: TestClient) -> str:
    """Upload SAMPLE_PPTX and return the job_id."""
    with SAMPLE_PPTX.open("rb") as f:
        resp = client.post(
            "/api/jobs",
            files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"allow_restructure": "false"},
        )
    assert resp.status_code == 201, f"upload failed: {resp.text}"
    data = resp.json()
    assert "jobId" in data, f"no jobId in response: {data}"
    return data["jobId"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sample_pptx_exists() -> None:
    assert SAMPLE_PPTX.exists(), f"Sample PPTX not found at {SAMPLE_PPTX}"


def test_upload_returns_job_id(client: TestClient) -> None:
    job_id = upload_sample(client)
    assert job_id  # non-empty string


def test_job_status_completed(client: TestClient) -> None:
    job_id = upload_sample(client)
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200, resp.text
    job = resp.json()
    assert job["status"] == "completed", f"unexpected status: {job['status']}"
    assert job["slideCount"] > 0, "slideCount should be > 0"


def test_result_returns_pptx_url(client: TestClient) -> None:
    job_id = upload_sample(client)
    resp = client.get(f"/api/jobs/{job_id}/result")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["pptxUrl"].endswith("output.pptx"), f"unexpected pptxUrl: {result['pptxUrl']}"


def test_pptx_download_is_valid(client: TestClient) -> None:
    """Download the output PPTX and verify it opens with python-pptx."""
    job_id = upload_sample(client)

    result_resp = client.get(f"/api/jobs/{job_id}/result")
    assert result_resp.status_code == 200
    pptx_url = result_resp.json()["pptxUrl"]

    dl_resp = client.get(pptx_url)
    assert dl_resp.status_code == 200, f"download failed: {dl_resp.status_code}"
    assert dl_resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

    prs = Presentation(io.BytesIO(dl_resp.content))
    assert len(prs.slides) > 0, "output PPTX has no slides"


def test_result_404_for_unknown_job(client: TestClient) -> None:
    resp = client.get("/api/jobs/nonexistent-job-id/result")
    assert resp.status_code == 404


def test_file_404_for_bad_filename(client: TestClient) -> None:
    job_id = upload_sample(client)
    resp = client.get(f"/api/jobs/{job_id}/files/../../etc/passwd")
    assert resp.status_code == 404
