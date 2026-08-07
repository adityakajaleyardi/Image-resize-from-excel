"""The HTTP surface of the flatten tool."""

from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("flatten_pdf")

from app.main import app  # noqa: E402
from tests.test_flatten_runner import form_pdf  # noqa: E402

OPTIONS = {
    "engine": "auto",
    "verify": "1",
    "verify_dpi": "72",
    "tolerance": "0.005",
    "allow_raster": "0",
    "raster_dpi": "150",
    "flatten_annots": "1",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import jobs

    monkeypatch.setattr(jobs.job_manager, "_jobs_dir", tmp_path / "jobs")
    with TestClient(app) as test_client:
        yield test_client


def upload(client, files, data=None):
    payload = {**OPTIONS, "paths": [name for name, _ in files], **(data or {})}
    return client.post(
        "/api/flatten/jobs",
        files=[("files", (name, content, "application/pdf")) for name, content in files],
        data=payload,
    )


def wait_for_finish(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["finished"]:
            return state
        time.sleep(0.1)
    raise AssertionError("The job did not finish in time.")


class TestPages:
    def test_the_run_page_renders(self, client):
        response = client.get("/flatten")
        assert response.status_code == 200
        assert "Flatten PDFs" in response.text
        assert "webkitdirectory" in response.text
        assert "Advanced" in response.text

    def test_the_help_page_explains_the_three_outcomes(self, client):
        response = client.get("/flatten/help")
        assert response.status_code == 200
        assert "Needs review" in response.text
        assert "Flatten_Report.csv" in response.text


class TestWhenTheLibraryIsMissing:
    @pytest.fixture(autouse=True)
    def hide_the_library(self, monkeypatch):
        from app import registry

        monkeypatch.setattr(registry, "find_spec", lambda name: None)

    def test_the_page_explains_how_to_install_it(self, client):
        response = client.get("/flatten")
        assert response.status_code == 200
        assert "not installed on this server" in response.text
        assert "pip install git+https" in response.text

    def test_starting_a_run_is_refused(self, client):
        response = upload(client, [("a.pdf", form_pdf())])
        assert response.status_code == 503
        assert "not installed" in response.json()["detail"]

    def test_the_other_tools_still_work(self, client):
        assert client.get("/images").status_code == 200


class TestJobCreation:
    def test_a_non_pdf_is_refused(self, client):
        response = upload(client, [("notes.txt", b"hello")])
        assert response.status_code == 400
        assert "not a PDF" in response.json()["detail"]

    def test_an_empty_selection_is_refused(self, client):
        response = client.post("/api/flatten/jobs", files=[("files", ("", b""))], data=OPTIONS)
        assert response.status_code in (400, 422)

    def test_too_many_files_are_refused(self, client, monkeypatch):
        from app.tools.flatten import routes

        monkeypatch.setattr(routes, "MAX_FILES", 2)
        response = upload(client, [(f"doc{index}.pdf", form_pdf()) for index in range(3)])
        assert response.status_code == 400
        assert "at most 2" in response.json()["detail"]

    def test_an_impossible_setting_is_rejected(self, client):
        response = upload(client, [("a.pdf", form_pdf())], data={"engine": "magic"})
        assert response.status_code == 400
        assert "Engine must be one of" in response.json()["detail"]


class TestJobLifecycle:
    def test_a_batch_completes_and_produces_a_zip(self, client):
        created = upload(client, [("first.pdf", form_pdf()), ("second.pdf", form_pdf())])
        assert created.status_code == 200

        state = wait_for_finish(client, created.json()["id"])
        assert state["status"] == "completed"
        assert state["tool"] == "flatten"
        assert state["summary"]["flattened"] == 2
        assert state["has_results"]
        assert state["has_log"]

        archive = client.get(f"/api/jobs/{created.json()['id']}/download")
        assert archive.status_code == 200
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            assert set(bundle.namelist()) == {
                "first.pdf",
                "second.pdf",
                "Flatten_Report.csv",
            }

    def test_the_folder_structure_survives_the_round_trip(self, client):
        created = client.post(
            "/api/flatten/jobs",
            files=[("files", ("march.pdf", form_pdf(), "application/pdf"))],
            data={**OPTIONS, "paths": ["Invoices/2024/march.pdf"]},
        )
        job_id = created.json()["id"]
        wait_for_finish(client, job_id)

        archive = client.get(f"/api/jobs/{job_id}/download")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            assert "Invoices/2024/march.pdf" in bundle.namelist()

    def test_a_hostile_path_cannot_escape_the_workspace(self, client):
        created = client.post(
            "/api/flatten/jobs",
            files=[("files", ("x.pdf", form_pdf(), "application/pdf"))],
            data={**OPTIONS, "paths": ["../../../../evil.pdf"]},
        )
        job_id = created.json()["id"]
        wait_for_finish(client, job_id)

        archive = client.get(f"/api/jobs/{job_id}/download")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            for name in bundle.namelist():
                assert ".." not in name

    def test_the_report_can_be_downloaded_on_its_own(self, client):
        created = upload(client, [("a.pdf", form_pdf())])
        job_id = created.json()["id"]
        wait_for_finish(client, job_id)

        report = client.get(f"/api/jobs/{job_id}/log")
        assert report.status_code == 200
        assert "Flatten_Report.csv" in report.headers["content-disposition"]
        assert "Status" in report.text


class TestDefaultOptions:
    def test_saving_a_default_changes_what_is_returned(self, client, tmp_path, monkeypatch):
        from app.tools.flatten import settings

        monkeypatch.setattr(settings, "DEFAULT_OPTIONS_PATH", tmp_path / "flatten.json")

        saved = client.post("/api/flatten/options/default", json={**OPTIONS, "raster_dpi": "300"})
        assert saved.status_code == 200
        assert client.get("/api/flatten/options/default").json()["raster_dpi"] == 300

    def test_an_impossible_default_is_rejected(self, client):
        response = client.post("/api/flatten/options/default", json={"verify_dpi": "9000"})
        assert response.status_code == 400
