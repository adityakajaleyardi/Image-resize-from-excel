"""The HTTP surface of the email converter."""

from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("greystar_email_converter")

from app.main import app  # noqa: E402
from tests.test_emails_runner import CSV_COLUMNS, LEGACY_COLUMNS, body  # noqa: E402

OPTIONS = {"column_layout": "auto", "render_images": "0"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import jobs

    monkeypatch.setattr(jobs.job_manager, "_jobs_dir", tmp_path / "jobs")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def with_binary(monkeypatch, tmp_path):
    """Pretend wkhtmltoimage is installed, whatever this machine actually has."""
    from app.tools.emails import routes

    monkeypatch.setattr(routes, "renderer_path", lambda: tmp_path / "wkhtmltoimage")


@pytest.fixture
def without_binary(monkeypatch):
    from app.tools.emails import routes

    monkeypatch.setattr(routes, "renderer_path", lambda: None)


def export_csv(rows, columns=CSV_COLUMNS) -> bytes:
    body_column, name_column = columns
    lines = [f"{name_column},{body_column}"]
    lines.extend(f"{record_id},{encoded}" for record_id, encoded in rows)
    return ("\n".join(lines) + "\n").encode("utf-8")


def export_xlsx(rows, columns=CSV_COLUMNS) -> bytes:
    import pandas as pd

    body_column, name_column = columns
    frame = pd.DataFrame([{name_column: record_id, body_column: encoded} for record_id, encoded in rows])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def upload(client, content=None, name="EmailBody.csv", data=None):
    if content is None:
        content = export_csv([("6111692732", body())])
    return client.post(
        "/api/emails/jobs",
        files={"export": (name, content, "text/csv")},
        data={**OPTIONS, **(data or {})},
    )


def wait_for_finish(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["finished"]:
            return state
        time.sleep(0.05)
    raise AssertionError("The job did not finish in time.")


class TestPages:
    def test_the_run_page_renders(self, client):
        response = client.get("/emails")
        assert response.status_code == 200
        assert "Emails to HTML and Images" in response.text
        assert "Detect from the file" in response.text

    def test_the_run_page_offers_both_layouts(self, client):
        response = client.get("/emails")
        assert "sBody / hResEmailLog" in response.text
        assert "sEmailMessage / hHistoryId" in response.text

    def test_the_help_page_explains_the_columns_and_the_output(self, client):
        response = client.get("/emails/help")
        assert response.status_code == 200
        assert "hResEmailLog" in response.text
        assert "Failed_Records.csv" in response.text

    def test_the_tool_is_in_the_navigation(self, client):
        assert '/emails"' in client.get("/images").text

    def test_the_home_page_offers_it_as_a_tile(self, client):
        response = client.get("/")
        assert "Emails to HTML and Images" in response.text
        assert 'href="/emails"' in response.text

    def test_the_short_retention_is_stated_on_the_page(self, client):
        from app.tools.emails.settings import RETENTION_HOURS

        response = client.get("/emails")
        assert f"after {RETENTION_HOURS} hours" in response.text


class TestWhenTheLibraryIsMissing:
    @pytest.fixture(autouse=True)
    def hide_the_library(self, monkeypatch):
        from app import registry

        monkeypatch.setattr(registry, "find_spec", lambda name: None)

    def test_the_page_explains_how_to_install_it(self, client):
        response = client.get("/emails")
        assert response.status_code == 200
        assert "not installed on this server" in response.text
        assert "requirements-emails.txt" in response.text

    def test_starting_a_run_is_refused(self, client):
        assert upload(client).status_code == 503

    def test_the_other_tools_still_work(self, client):
        assert client.get("/images").status_code == 200


class TestWhenTheBinaryIsMissing:
    def test_asking_for_screenshots_is_refused_with_a_way_out(self, client, without_binary):
        response = upload(client, data={"render_images": "1"})
        assert response.status_code == 400
        assert "wkhtmltoimage" in response.json()["detail"]
        assert "HTML only" in response.json()["detail"]

    def test_html_only_still_runs(self, client, without_binary):
        assert upload(client).status_code == 200

    def test_the_page_disables_the_screenshot_option(self, client, monkeypatch):
        from app.tools.emails import routes

        monkeypatch.setattr(routes, "renderer_path", lambda: None)
        response = client.get("/emails")
        assert "disabled" in response.text
        assert "wkhtmltoimage is not installed" in response.text


class TestJobCreation:
    def test_a_file_that_is_not_a_table_is_refused(self, client):
        response = upload(client, b"%PDF-1.4", name="notes.pdf")
        assert response.status_code == 400
        assert "not a CSV or Excel file" in response.json()["detail"]

    def test_an_empty_file_is_refused(self, client):
        response = upload(client, b"")
        assert response.status_code == 400
        assert "empty" in response.json()["detail"]

    def test_a_missing_file_is_refused(self, client):
        response = client.post("/api/emails/jobs", data=OPTIONS)
        assert response.status_code == 422

    def test_an_impossible_layout_is_rejected(self, client):
        response = upload(client, data={"column_layout": "guesswork"})
        assert response.status_code == 400
        assert "Column layout must be one of" in response.json()["detail"]

    def test_an_oversized_file_is_refused(self, client, monkeypatch):
        from app.tools.emails import routes

        monkeypatch.setattr(routes, "MAX_FILE_BYTES", 10)
        response = upload(client)
        assert response.status_code == 413

    def test_a_run_is_kept_for_less_time_than_the_rest(self, client):
        from app.jobs import job_manager
        from app.tools.emails.settings import RETENTION_HOURS

        job_id = upload(client).json()["id"]
        wait_for_finish(client, job_id)

        assert job_manager.get(job_id).retention_hours == RETENTION_HOURS


class TestJobLifecycle:
    def test_a_csv_converts_end_to_end(self, client):
        created = upload(client, export_csv([("a", body()), ("b", body())]))
        assert created.status_code == 200

        state = wait_for_finish(client, created.json()["id"])
        assert state["status"] == "completed"
        assert state["tool"] == "emails"
        assert state["summary"]["succeeded"] == 2
        assert state["summary"]["failed"] == 0
        assert state["has_results"]
        assert not state["has_log"]

        archive = client.get(f"/api/jobs/{created.json()['id']}/download")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            assert set(bundle.namelist()) == {"html/a.html", "html/b.html"}

    def test_an_excel_export_converts_end_to_end(self, client):
        created = upload(
            client,
            export_xlsx([("a", body())], columns=LEGACY_COLUMNS),
            name="Legacy.xlsx",
        )
        state = wait_for_finish(client, created.json()["id"])

        assert state["status"] == "completed"
        assert state["summary"]["columns"] == "sEmailMessage / hHistoryId"

    def test_a_wrong_column_file_fails_with_a_readable_message(self, client):
        created = upload(client, export_csv([("a", body())], columns=("Blob", "Reference")))
        state = wait_for_finish(client, created.json()["id"])

        assert state["status"] == "failed"
        assert "sBody and hResEmailLog" in state["error"]
        assert "sEmailMessage and hHistoryId" in state["error"]

    def test_bad_rows_do_not_stop_the_run_and_are_reported(self, client):
        created = upload(client, export_csv([("good", body()), ("bad", "@@@")]))
        job_id = created.json()["id"]
        state = wait_for_finish(client, job_id)

        assert state["status"] == "completed"
        assert state["summary"]["succeeded"] == 1
        assert state["summary"]["failed"] == 1
        assert state["summary"]["failures"][0]["record_id"] == "bad"
        assert state["has_log"]

        log = client.get(f"/api/jobs/{job_id}/log")
        assert log.status_code == 200
        assert "Failed_Records.csv" in log.headers["content-disposition"]
        assert "Error_Details" in log.text

    def test_the_log_offered_for_download_holds_no_email_bodies(self, client):
        encoded = body("Confidential lease terms")
        created = upload(client, export_csv([("bad", "@@@"), ("good", encoded)]))
        job_id = created.json()["id"]
        wait_for_finish(client, job_id)

        assert encoded not in client.get(f"/api/jobs/{job_id}/log").text

    def test_nothing_in_the_response_exposes_a_server_path(self, client):
        created = upload(client)
        state = wait_for_finish(client, created.json()["id"])

        rendered = str(state)
        assert "uploads" not in rendered
        assert "jobs" not in rendered
        assert ":\\" not in rendered

    def test_the_output_is_not_served_as_a_static_file(self, client):
        created = upload(client)
        wait_for_finish(client, created.json()["id"])

        assert client.get("/static/html/a.html").status_code == 404


class TestDefaultOptions:
    def test_saving_a_default_changes_what_is_returned(self, client, tmp_path, monkeypatch):
        from app.tools.emails import settings

        monkeypatch.setattr(settings, "DEFAULT_OPTIONS_PATH", tmp_path / "emails.json")

        saved = client.post(
            "/api/emails/options/default",
            json={"column_layout": "legacy_xlsx", "render_images": 0},
        )
        assert saved.status_code == 200

        current = client.get("/api/emails/options/default").json()
        assert current["column_layout"] == "legacy_xlsx"
        assert current["render_images"] is False

    def test_an_impossible_default_is_rejected(self, client):
        response = client.post("/api/emails/options/default", json={"column_layout": "nonsense"})
        assert response.status_code == 400
