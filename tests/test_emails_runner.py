"""The email converter run.

Every test here uses the real library, but never the real renderer: screenshots
shell out to wkhtmltoimage, which CI does not have. `stub_renderer` puts a fake
in its place so the image path is still covered.
"""

from __future__ import annotations

import csv
import io
import threading
from pathlib import Path

import pytest

pytest.importorskip("greystar_email_converter")

from greystar_email_converter import encode_email_body  # noqa: E402

from app.events import ToolError  # noqa: E402
from app.jobs import JobContext  # noqa: E402
from app.tools.emails.options import (  # noqa: E402
    LAYOUT_CSV_EXPORT,
    LAYOUT_LEGACY_XLSX,
    EmailSettings,
)
from app.tools.emails.runner import build_runner  # noqa: E402
from app.tools.emails.settings import (  # noqa: E402
    FAILURE_LOG_NAME,
    HTML_DIR_NAME,
    IMAGE_DIR_NAME,
)

CSV_COLUMNS = ("sBody", "hResEmailLog")
LEGACY_COLUMNS = ("sEmailMessage", "hHistoryId")


def body(text: str = "Dear resident, your lease renews soon.") -> str:
    return encode_email_body(f"<html><body><p>{text}</p></body></html>")


class Run:
    """One runner invocation, and everything it wrote or reported."""

    def __init__(self, tmp_path: Path) -> None:
        self.uploads = tmp_path / "uploads"
        self.output = tmp_path / "output"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=True)
        self.events: list = []
        self.cancel = threading.Event()
        #: Set to a record number to cancel the run once it gets that far.
        self.cancel_after: int | None = None

    def write_export(
        self,
        rows: list[tuple[str, str]],
        *,
        columns: tuple[str, str] = CSV_COLUMNS,
        extra: dict[str, str] | None = None,
        name: str = "EmailBody.csv",
    ) -> Path:
        """An export shaped like the real one: an id column, noise, then the body."""
        name_column, body_column = columns[1], columns[0]
        extra = extra or {}
        path = self.uploads / name

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([name_column, *extra, body_column])
            for record_id, encoded in rows:
                writer.writerow([record_id, *extra.values(), encoded])
        return path

    def go(self, **overrides) -> dict:
        settings = EmailSettings(**{"render_images": False, **overrides})
        return build_runner(settings)(self._context())

    def _context(self) -> JobContext:
        return JobContext(
            uploads_dir=self.uploads,
            output_dir=self.output,
            emit=self._emit,
            cancel=self.cancel,
        )

    def _emit(self, event) -> None:
        self.events.append(event)
        if self.cancel_after and event.processed == self.cancel_after:
            self.cancel.set()

    def messages(self, level: str) -> list[str]:
        return [event.message for event in self.events if event.level == level]

    def html_files(self) -> set[str]:
        return self._names(HTML_DIR_NAME)

    def images(self) -> set[str]:
        return self._names(IMAGE_DIR_NAME)

    def _names(self, folder: str) -> set[str]:
        directory = self.output / folder
        return {path.name for path in directory.iterdir()} if directory.exists() else set()

    def failure_log(self) -> list[dict[str, str]]:
        path = self.output / FAILURE_LOG_NAME
        if not path.exists():
            return []
        return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


@pytest.fixture
def run(tmp_path) -> Run:
    return Run(tmp_path)


@pytest.fixture
def stub_renderer(monkeypatch):
    """Stand in for wkhtmltoimage so the image path needs no binary."""
    from greystar_email_converter import pipeline

    class StubRenderer:
        def __init__(self, *, executable=None, options=None) -> None:
            self.options = options

        def render_file(self, html_path, output_path, *, width: int) -> None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"\xff\xd8\xff" + str(width).encode())

    monkeypatch.setattr(pipeline, "ImageRenderer", StubRenderer)


@pytest.fixture
def no_binary(monkeypatch):
    """A server where the library is installed but wkhtmltoimage is not."""
    from greystar_email_converter import RendererNotFoundError, renderer

    def missing(explicit=None):
        raise RendererNotFoundError("wkhtmltoimage was not found.")

    monkeypatch.setattr(renderer, "find_wkhtmltoimage", missing)


class TestAGoodRun:
    def test_every_record_becomes_an_html_file(self, run):
        run.write_export([("6111692732", body()), ("6111692733", body())])

        summary = run.go()

        assert summary["succeeded"] == 2
        assert summary["failed"] == 0
        assert summary["total"] == 2
        assert run.html_files() == {"6111692732.html", "6111692733.html"}

    def test_the_decoded_html_is_the_original(self, run):
        run.write_export([("77", body("Renewal offer inside"))])

        run.go()

        written = (run.output / HTML_DIR_NAME / "77.html").read_text(encoding="utf-8")
        assert "Renewal offer inside" in written

    def test_progress_is_reported_once_per_record(self, run):
        run.write_export([(str(index), body()) for index in range(5)])

        run.go()

        progress = [event for event in run.events if event.processed]
        assert [event.processed for event in progress] == [1, 2, 3, 4, 5]
        assert {event.total for event in progress} == {5}

    def test_rows_are_numbered_as_spreadsheet_lines(self, run):
        run.write_export([("a", body()), ("b", body())])

        run.go()

        assert [event.row for event in run.events if event.row] == [2, 3]

    def test_no_failure_log_is_written_when_nothing_fails(self, run):
        run.write_export([("a", body())])

        run.go()

        assert not (run.output / FAILURE_LOG_NAME).exists()


class TestChoosingTheColumns:
    def test_the_csv_layout_is_detected(self, run):
        run.write_export([("a", body())], columns=CSV_COLUMNS)

        summary = run.go()

        assert summary["columns"] == "sBody / hResEmailLog"
        assert any("Detected" in message for message in run.messages("info"))

    def test_the_legacy_layout_is_detected(self, run):
        run.write_export([("a", body())], columns=LEGACY_COLUMNS)

        summary = run.go()

        assert summary["columns"] == "sEmailMessage / hHistoryId"

    def test_a_chosen_layout_is_used_as_given(self, run):
        run.write_export([("a", body())], columns=LEGACY_COLUMNS)

        summary = run.go(column_layout=LAYOUT_LEGACY_XLSX)

        assert summary["columns"] == "sEmailMessage / hHistoryId"

    def test_a_file_in_neither_layout_names_both(self, run):
        run.write_export([("a", body())], columns=("Blob", "Reference"))

        with pytest.raises(ToolError) as raised:
            run.go()

        message = str(raised.value)
        assert "sBody and hResEmailLog" in message
        assert "sEmailMessage and hHistoryId" in message
        assert "Blob" in message

    def test_choosing_the_wrong_layout_says_which_column_is_missing(self, run):
        run.write_export([("a", body())], columns=LEGACY_COLUMNS)

        with pytest.raises(ToolError) as raised:
            run.go(column_layout=LAYOUT_CSV_EXPORT)

        message = str(raised.value)
        assert "sBody" in message
        assert "other column layout" in message


class TestBadRecords:
    def test_one_bad_record_does_not_stop_the_batch(self, run):
        run.write_export([("good-1", body()), ("bad", "not base64 at all!"), ("good-2", body())])

        summary = run.go()

        assert summary["succeeded"] == 2
        assert summary["failed"] == 1
        assert run.html_files() == {"good-1.html", "good-2.html"}

    def test_an_empty_body_is_a_failure_not_a_crash(self, run):
        run.write_export([("blank", "")])

        summary = run.go()

        assert summary["failed"] == 1
        assert summary["failures"][0]["record_id"] == "blank"
        assert summary["failures"][0]["error"]

    def test_failures_are_written_to_a_log(self, run):
        run.write_export([("good", body()), ("bad", "@@@")])

        run.go()

        rows = run.failure_log()
        assert len(rows) == 1
        assert rows[0]["Record_Id"] == "bad"
        assert rows[0]["Row_Index"] == "3"
        assert rows[0]["Error_Details"]

    def test_the_failure_log_keeps_the_other_columns(self, run):
        run.write_export([("bad", "@@@")], extra={"sPropertyCode": "p1812741"})

        run.go()

        assert run.failure_log()[0]["sPropertyCode"] == "p1812741"

    def test_the_reason_is_readable_and_quotes_no_raw_bytes(self, run):
        run.write_export([("bad", "corrupt-value")])

        summary = run.go()

        reason = summary["failures"][0]["error"]
        assert "does not look like a compressed email body" in reason
        assert "first bytes" not in reason
        assert "\\x" not in reason

    def test_the_failure_log_does_not_carry_the_email_body(self, run):
        encoded = body("Confidential lease terms")
        run.write_export([("bad", "@@@"), ("good", encoded)])

        run.go()

        raw = (run.output / FAILURE_LOG_NAME).read_text(encoding="utf-8-sig")
        assert "sBody" not in raw
        assert encoded not in raw


class TestRefusingToStart:
    def test_a_file_with_no_rows_is_refused(self, run):
        run.write_export([])

        with pytest.raises(ToolError, match="no rows"):
            run.go()

    def test_a_format_that_cannot_be_read_is_refused(self, run):
        (run.uploads / "export.docx").write_bytes(b"not a table")

        with pytest.raises(ToolError, match="docx"):
            run.go()

    def test_an_empty_workspace_is_refused(self, run):
        with pytest.raises(ToolError, match="No file was uploaded"):
            run.go()


class TestCancelling:
    def test_a_cancelled_run_stops_early_and_keeps_its_output(self, run):
        run.write_export([(str(index), body()) for index in range(10)])
        run.cancel_after = 2

        summary = run.go()

        assert summary["processed"] == 2
        assert summary["succeeded"] == 2
        assert summary["total"] == 10
        assert run.html_files() == {"0.html", "1.html"}
        assert any("Cancelled" in message for message in run.messages("warning"))


class TestScreenshots:
    def test_an_image_is_written_for_every_record(self, run, stub_renderer):
        run.write_export([("a", body()), ("b", body())])

        summary = run.go(render_images=True)

        assert summary["images"] == 2
        assert summary["html_only"] is False
        assert run.images() == {"a.jpg", "b.jpg"}

    def test_the_width_is_read_from_the_email(self, run, stub_renderer):
        narrow = encode_email_body('<html><body><table width="640"></table></body></html>')
        run.write_export([("a", narrow)])

        run.go(render_images=True)

        assert (run.output / IMAGE_DIR_NAME / "a.jpg").read_bytes() == b"\xff\xd8\xff640"

    def test_html_only_writes_no_images(self, run):
        run.write_export([("a", body())])

        summary = run.go()

        assert summary["html_only"] is True
        assert summary["images"] == 0
        assert run.images() == set()

    def test_a_missing_binary_says_to_turn_screenshots_off(self, run, no_binary):
        run.write_export([("a", body())])

        with pytest.raises(ToolError, match="screenshots turned off"):
            run.go(render_images=True)

    def test_a_missing_binary_is_caught_before_the_first_record(self, run, no_binary):
        run.write_export([("a", body())])

        with pytest.raises(ToolError):
            run.go(render_images=True)

        assert run.html_files() == set()

    def test_html_only_still_works_without_the_binary(self, run, no_binary):
        run.write_export([("a", body())])

        assert run.go()["succeeded"] == 1
