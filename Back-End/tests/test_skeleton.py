"""Integration test: walking skeleton end-to-end roundtrip.

Upload the committed sample PPTX → plan_ready → approve → completed
→ assert PPTX download works. The output PPTX must be openable by
python-pptx with at least one slide.

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
from app.services import job_engine as _je
from app.services.job_engine import InProcessJobEngine

# The committed sample deck — a valid 6-slide branded PPTX
SAMPLE_PPTX = Path(__file__).parent.parent / "out" / "samples_imocha_template.pptx"


@pytest.fixture(scope="module", autouse=True)
def _inline_engine() -> None:  # type: ignore[return]
    """Use inline engine so the full pipeline completes synchronously."""
    _je.init_engine(InProcessJobEngine(inline=True))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def upload_sample(client: TestClient) -> str:
    """Upload SAMPLE_PPTX, approve the plan, and return the completed job_id."""
    with SAMPLE_PPTX.open("rb") as f:
        resp = client.post(
            "/api/jobs",
            files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"allow_restructure": "false"},
        )
    assert resp.status_code == 201, f"upload failed: {resp.text}"
    data = resp.json()
    assert "jobId" in data, f"no jobId in response: {data}"
    job_id = data["jobId"]

    # Approve the plan to trigger segment B (synchronous in inline mode).
    approve = client.post(f"/api/jobs/{job_id}/plan/approve")
    assert approve.status_code == 202, f"approve failed: {approve.text}"

    return job_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_sample_pptx_exists() -> None:
    assert SAMPLE_PPTX.exists(), f"Sample PPTX not found at {SAMPLE_PPTX}"


def test_upload_returns_job_id(client: TestClient) -> None:
    with SAMPLE_PPTX.open("rb") as f:
        resp = client.post(
            "/api/jobs",
            files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"allow_restructure": "false"},
        )
    assert resp.status_code == 201
    job_id = resp.json().get("jobId", "")
    assert job_id  # non-empty string


def test_job_reaches_plan_ready_before_approve(client: TestClient) -> None:
    """Segment A alone → plan_ready (not completed)."""
    with SAMPLE_PPTX.open("rb") as f:
        resp = client.post(
            "/api/jobs",
            files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"allow_restructure": "false"},
        )
    job_id = resp.json()["jobId"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "plan_ready"
    assert job["slideCount"] > 0
    assert isinstance(job["plan"], list)
    assert len(job["plan"]) > 0


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
