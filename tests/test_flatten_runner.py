"""The flatten runner, driven through the real library on real PDFs.

The point of these tests is the batch behaviour the web app adds: where files are
written, what the report says, and that one bad document does not take the run
down with it. How well any given PDF flattens is the library's own business.
"""

from __future__ import annotations

import csv
import threading

import pytest

pytest.importorskip("flatten_pdf")
fitz = pytest.importorskip("fitz")

from app.events import ToolError  # noqa: E402
from app.jobs import JobContext  # noqa: E402
from app.tools.flatten.options import FlattenSettings  # noqa: E402
from app.tools.flatten.runner import (  # noqa: E402
    REPORT_COLUMNS,
    STATUS_FAILED,
    STATUS_FLATTENED,
    build_runner,
)
from app.tools.flatten.settings import REPORT_NAME  # noqa: E402


def form_pdf(value: str = "Filled in") -> bytes:
    """A one page PDF with a filled in text field, which is the case that matters."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Statement of account", fontsize=18)

    widget = fitz.Widget()
    widget.field_name = "customer"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = fitz.Rect(72, 100, 320, 130)
    widget.field_value = value
    page.add_widget(widget)

    return document.tobytes()


def count_widgets(data: bytes) -> int:
    document = fitz.open(stream=data, filetype="pdf")
    return sum(len(list(page.widgets() or [])) for page in document)


@pytest.fixture
def workspace(tmp_path):
    """An uploads and output pair, plus the events the runner emitted."""
    uploads = tmp_path / "uploads"
    output = tmp_path / "output"
    uploads.mkdir()
    output.mkdir()

    events = []
    cancel = threading.Event()
    context = JobContext(uploads_dir=uploads, output_dir=output, emit=events.append, cancel=cancel)
    return context, events


def run_batch(context, settings=None):
    return build_runner(settings or FlattenSettings())(context)


def read_report(output_dir):
    with (output_dir / REPORT_NAME).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class TestASuccessfulBatch:
    def test_a_form_pdf_comes_back_without_its_fields(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "statement.pdf").write_bytes(form_pdf())

        summary = run_batch(context)

        assert summary["flattened"] == 1
        assert summary["failed"] == 0
        assert summary["review"] == 0

        result = context.output_dir / "statement.pdf"
        assert result.exists()
        assert count_widgets(result.read_bytes()) == 0

    def test_the_folder_structure_is_preserved(self, workspace):
        context, _ = workspace
        nested = context.uploads_dir / "Invoices" / "2024"
        nested.mkdir(parents=True)
        (nested / "march.pdf").write_bytes(form_pdf())

        run_batch(context)

        assert (context.output_dir / "Invoices" / "2024" / "march.pdf").exists()

    def test_progress_is_reported_once_per_file(self, workspace):
        context, events = workspace
        for index in range(3):
            (context.uploads_dir / f"doc{index}.pdf").write_bytes(form_pdf())

        run_batch(context)

        per_file = [event for event in events if event.processed]
        assert [event.processed for event in per_file] == [1, 2, 3]
        assert all(event.total == 3 for event in per_file)

    def test_the_report_has_a_row_for_every_file(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "a.pdf").write_bytes(form_pdf())
        (context.uploads_dir / "b.pdf").write_bytes(form_pdf())

        run_batch(context)

        rows = read_report(context.output_dir)
        assert [row["File"] for row in rows] == ["a.pdf", "b.pdf"]
        assert {row["Status"] for row in rows} == {STATUS_FLATTENED}
        assert list(rows[0]) == list(REPORT_COLUMNS)
        assert rows[0]["Engine"]

    def test_the_report_travels_with_the_results(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "a.pdf").write_bytes(form_pdf())

        run_batch(context)

        assert (context.output_dir / REPORT_NAME).exists()


class TestWhenAFileIsBad:
    def test_a_corrupt_file_fails_without_ending_the_batch(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "broken.pdf").write_bytes(b"this is not a PDF at all")
        (context.uploads_dir / "fine.pdf").write_bytes(form_pdf())

        summary = run_batch(context)

        assert summary["failed"] == 1
        assert summary["flattened"] == 1
        assert (context.output_dir / "fine.pdf").exists()
        assert not (context.output_dir / "broken.pdf").exists()

    def test_a_failure_is_explained_in_the_report(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "broken.pdf").write_bytes(b"this is not a PDF at all")

        run_batch(context)

        row = read_report(context.output_dir)[0]
        assert row["Status"] == STATUS_FAILED
        assert row["Detail"]

    def test_a_failure_is_flagged_in_the_summary(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "broken.pdf").write_bytes(b"this is not a PDF at all")

        summary = run_batch(context)

        assert [item["name"] for item in summary["flagged"]] == ["broken.pdf"]
        assert summary["flagged"][0]["status"] == STATUS_FAILED


class TestEdgeCases:
    def test_an_empty_upload_folder_is_a_clear_error(self, workspace):
        context, _ = workspace
        with pytest.raises(ToolError, match="nothing to flatten"):
            run_batch(context)

    def test_non_pdf_files_in_the_folder_are_ignored(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "notes.txt").write_bytes(b"ignore me")
        (context.uploads_dir / "real.pdf").write_bytes(form_pdf())

        summary = run_batch(context)

        assert summary["total"] == 1

    def test_cancelling_stops_the_batch_and_keeps_what_was_done(self, workspace):
        context, events = workspace
        for index in range(5):
            (context.uploads_dir / f"doc{index}.pdf").write_bytes(form_pdf())

        # Ask to stop as soon as the first file has been dealt with.
        def stop_after_first(event):
            events.append(event)
            if event.processed >= 1:
                context.cancel.set()

        context = JobContext(
            uploads_dir=context.uploads_dir,
            output_dir=context.output_dir,
            emit=stop_after_first,
            cancel=context.cancel,
        )

        summary = run_batch(context)

        assert summary["cancelled"] is True
        assert summary["total"] == 5
        assert summary["flattened"] == 1
        assert summary["skipped"] == 4
        assert (context.output_dir / "doc0.pdf").exists()

    def test_turning_verification_off_still_produces_a_result(self, workspace):
        context, _ = workspace
        (context.uploads_dir / "statement.pdf").write_bytes(form_pdf())

        summary = run_batch(context, FlattenSettings(verify=False))

        assert summary["flattened"] == 1
        assert count_widgets((context.output_dir / "statement.pdf").read_bytes()) == 0
