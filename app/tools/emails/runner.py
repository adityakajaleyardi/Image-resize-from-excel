"""The email converter run.

Reads the uploaded export, then hands the library one record at a time so the
browser sees per-record progress and a cancel takes effect within a second. The
library owns all the decoding, width detection and rendering; nothing here
reproduces any of it.

The library is imported inside the runner so a server without it still starts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ...events import Event, ToolError
from ...jobs import JobContext
from .options import LAYOUT_COLUMNS, EmailSettings
from .settings import FAILURE_LOG_NAME, HTML_DIR_NAME, IMAGE_DIR_NAME

logger = logging.getLogger(__name__)

#: Enough for the results card to be useful without posting a novel to the
#: browser on every poll. The downloadable log always has all of them.
MAX_REPORTED_FAILURES = 50

# The decoder quotes the start of a value it could not read. That means nothing
# to the person running this, and it is the one place raw bytes from the source
# column would otherwise reach the screen and the log.
_RAW_BYTES = re.compile(r"\s*\(first bytes: .*?\)")


def build_runner(settings: EmailSettings):
    def run(context: JobContext) -> dict[str, Any]:
        from greystar_email_converter import (
            ConversionReport,
            EmailConverter,
            RendererNotFoundError,
        )

        frame = _read_table(_source_file(context.uploads_dir))
        columns = _resolve_columns(frame.columns, settings, context)

        total = len(frame)
        if not total:
            raise ToolError("The file has a header but no rows, so there was nothing to convert.")

        html_dir = context.output_dir / HTML_DIR_NAME
        image_dir = context.output_dir / IMAGE_DIR_NAME if settings.render_images else None

        converter = EmailConverter(
            columns=columns,
            # Each run has its own empty workspace, so this only matters when a
            # record id repeats: the first output wins instead of being redone.
            skip_existing=True,
            render_images=settings.render_images,
        )

        if image_dir is not None:
            try:
                # Resolve the executable before the first record rather than
                # failing an hour into a run.
                _ = converter.renderer
            except RendererNotFoundError as error:
                raise ToolError(
                    "Screenshots were requested but wkhtmltoimage is not installed on this "
                    "server, so no images can be produced. Run again with screenshots turned "
                    f"off to get the HTML, or ask for it to be installed. ({error})"
                ) from error

        context.emit(
            Event(
                "info",
                f"Converting {total} record{'' if total == 1 else 's'} "
                f"using {columns.body} and {columns.name}.",
                total=total,
            )
        )

        report = ConversionReport()
        rendered = 0

        for position, (_, row) in enumerate(frame.iterrows(), start=1):
            # Spreadsheet line number: the header is line 1, so data starts at 2.
            line = position + 1
            result = converter.convert_row(
                row.get(columns.body),
                row.get(columns.name),
                html_dir=html_dir,
                image_dir=image_dir,
                row_index=line,
                # The body is dropped: the failure log is downloaded by a user
                # and does not need a copy of the email in it.
                source_row=_without_body(row, columns.body),
            )
            if result.error:
                result.error = _RAW_BYTES.sub("", result.error)
            report.results.append(result)
            if result.image_path is not None:
                rendered += 1

            context.emit(
                Event(
                    "ok" if result.succeeded else "fail",
                    _describe(result, settings.render_images),
                    row=line,
                    processed=position,
                    total=total,
                )
            )

            if context.cancel.is_set():
                context.emit(Event("warning", "Cancelled. Keeping what was produced so far."))
                break

        report.write_failure_log(context.output_dir / FAILURE_LOG_NAME)

        return {
            "total": total,
            "processed": len(report.results),
            "succeeded": report.succeeded,
            "failed": report.failed,
            "images": rendered,
            "html_only": not settings.render_images,
            "columns": f"{columns.body} / {columns.name}",
            "failures": [
                {"record_id": result.record_id, "error": result.error}
                for result in report.failures[:MAX_REPORTED_FAILURES]
            ],
        }

    return run


def _source_file(uploads_dir: Path) -> Path:
    files = sorted(path for path in uploads_dir.iterdir() if path.is_file())
    if not files:
        raise ToolError("No file was uploaded.")
    return files[0]


def _read_table(source: Path):
    from greystar_email_converter import UnsupportedInputError, read_table

    try:
        return read_table(source)
    except UnsupportedInputError as error:
        raise ToolError(str(error)) from error
    except ValueError as error:
        # A CSV whose rows do not line up, or a workbook pandas cannot parse.
        raise ToolError(f"{source.name} could not be read as a table: {error}") from error


def _resolve_columns(available, settings: EmailSettings, context: JobContext):
    """The column layout to read, detected from the headings when asked."""
    from greystar_email_converter import ColumnMapping, MissingColumnError

    chosen = settings.to_column_mapping()
    if chosen is not None:
        try:
            chosen.validate(available)
        except MissingColumnError as error:
            raise ToolError(f"{error} Try the other column layout, or let the file be detected.") from error
        return chosen

    for candidate in (ColumnMapping.csv_export(), ColumnMapping.legacy_xlsx()):
        try:
            candidate.validate(available)
        except MissingColumnError:
            continue
        context.emit(Event("info", f"Detected the {candidate.body} / {candidate.name} layout."))
        return candidate

    expected = " or ".join(f"{body} and {name}" for body, name in LAYOUT_COLUMNS.values())
    raise ToolError(
        f"This file does not hold email bodies in a layout this tool knows. It needs "
        f"{expected}. The file has: {', '.join(str(column) for column in available) or '(no columns)'}."
    )


def _without_body(row, body_column: str) -> dict[str, Any]:
    return {name: value for name, value in row.items() if name != body_column}


def _describe(result, wanted_images: bool) -> str:
    if not result.succeeded:
        return f"{result.record_id}: {result.error}"
    if result.image_path is not None:
        return f"{result.record_id} converted, rendered {result.width}px wide"
    if wanted_images:
        return f"{result.record_id} converted, no image produced"
    return f"{result.record_id} converted to HTML"
