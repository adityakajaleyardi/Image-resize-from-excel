"""The HTTP surface, including the errors a user is most likely to hit."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import SOURCE_HEADER

VALID_SETTINGS = {
    "operationmode": "2",
    "propertytype": "MVC",
    "manualsizing": "0",
    "targetwidth": "2560",
    "targetheight": "1707",
    "maxfilesizemb": "1.0",
    "optimizedsuffix": "0",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client whose jobs are written to a throwaway directory."""
    from app import jobs

    monkeypatch.setattr(jobs.job_manager, "_jobs_dir", tmp_path / "jobs")
    with TestClient(app) as test_client:
        yield test_client


def source_csv(image_server, rows=None):
    rows = rows or [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
    return "\n".join([SOURCE_HEADER, *rows]) + "\n"


def wait_for_finish(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["finished"]:
            return state
        time.sleep(0.1)
    raise AssertionError("The job did not finish in time.")


class TestPages:
    def test_the_run_page_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Process property images" in response.text

    def test_the_help_page_lists_the_required_columns(self, client):
        response = client.get("/help")
        assert response.status_code == 200
        assert "Doc. Type" in response.text
        assert "Target Image Name" in response.text

    def test_templates_can_be_downloaded(self, client):
        response = client.get("/api/templates/source")
        assert response.status_code == 200
        assert "Full Path" in response.text

    def test_an_unknown_template_is_not_found(self, client):
        assert client.get("/api/templates/secrets").status_code == 404


class TestDefaultConfig:
    def test_saving_a_default_changes_what_is_returned(self, client, tmp_path, monkeypatch):
        from app import main, settings

        monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
        monkeypatch.setattr(settings, "DEFAULT_CONFIG_PATH", tmp_path / "default_config.json")
        monkeypatch.setattr(main, "save_default_config", settings.save_default_config)
        monkeypatch.setattr(main, "load_default_config", settings.load_default_config)

        saved = client.post("/api/config/default", json={**VALID_SETTINGS, "maxfilesizemb": "4.5"})
        assert saved.status_code == 200
        assert client.get("/api/config/default").json()["maxfilesizemb"] == 4.5

    def test_an_impossible_setting_is_rejected(self, client):
        response = client.post("/api/config/default", json={**VALID_SETTINGS, "operationmode": "7"})
        assert response.status_code == 400
        assert "Operation mode" in response.json()["detail"]


class TestJobCreation:
    def test_a_missing_column_is_reported_before_the_job_starts(self, client):
        response = client.post(
            "/api/jobs",
            files={"source": ("Source.csv", "Property Code,File Name\np1,x.jpg\n", "text/csv")},
            data=VALID_SETTINGS,
        )
        assert response.status_code == 400
        assert "Full Path" in response.json()["detail"]

    def test_a_non_csv_upload_is_refused(self, client):
        response = client.post(
            "/api/jobs",
            files={"source": ("Source.xlsx", b"not a csv", "application/vnd.ms-excel")},
            data=VALID_SETTINGS,
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_an_empty_upload_is_refused(self, client):
        response = client.post(
            "/api/jobs",
            files={"source": ("Source.csv", b"", "text/csv")},
            data=VALID_SETTINGS,
        )
        assert response.status_code == 400

    def test_a_bad_mapping_file_is_reported(self, client, image_server):
        response = client.post(
            "/api/jobs",
            files={
                "source": ("Source.csv", source_csv(image_server), "text/csv"),
                "property_map": ("PropertyHMY.csv", "Name,Town\na,b\n", "text/csv"),
            },
            data=VALID_SETTINGS,
        )
        assert response.status_code == 400
        assert "Propery Code" in response.json()["detail"]


class TestJobLifecycle:
    def test_a_run_completes_and_produces_a_download(self, client, image_server):
        created = client.post(
            "/api/jobs",
            files={"source": ("Source.csv", source_csv(image_server), "text/csv")},
            data=VALID_SETTINGS,
        )
        assert created.status_code == 200
        job_id = created.json()["id"]

        state = wait_for_finish(client, job_id)
        assert state["status"] == "completed"
        assert state["summary"]["succeeded"] == 1
        assert state["has_results"]

        archive = client.get(f"/api/jobs/{job_id}/download")
        assert archive.status_code == 200
        assert archive.headers["content-type"] == "application/zip"

        log = client.get(f"/api/jobs/{job_id}/log")
        assert log.status_code == 200

    def test_polling_with_a_cursor_only_returns_new_events(self, client, image_server):
        job_id = client.post(
            "/api/jobs",
            files={"source": ("Source.csv", source_csv(image_server), "text/csv")},
            data=VALID_SETTINGS,
        ).json()["id"]

        wait_for_finish(client, job_id)
        full = client.get(f"/api/jobs/{job_id}", params={"cursor": 0}).json()
        assert full["events"]

        tail = client.get(f"/api/jobs/{job_id}", params={"cursor": full["cursor"]}).json()
        assert tail["events"] == []

    def test_an_unknown_job_is_not_found(self, client):
        response = client.get("/api/jobs/does-not-exist")
        assert response.status_code == 404
        assert "expired" in response.json()["detail"]
