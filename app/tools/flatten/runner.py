"""Running a batch of uploaded PDFs through the flatten-pdf library.

One file at a time, in a worker thread, so the batch never becomes a single long
request. The library decides how to flatten and whether the result is trustworthy;
this module only handles the batch, the report and the progress the browser sees.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...events import LEVEL_FAIL, LEVEL_INFO, LEVEL_OK, LEVEL_WARNING, Event, ToolError
from ...jobs import JobContext
from .options import FlattenSettings
from .settings import REPORT_NAME

STATUS_FLATTENED = "Flattened"
STATUS_REVIEW = "Needs review"
STATUS_FAILED = "Failed"

REPORT_COLUMNS = (
    "File",
    "Status",
    "Engine",
    "Detail",
    "Content lost %",
    "Content gained %",
    "Engines tried",
)

INSTALL_HINT = (
    "The PDF flattening library is not installed on this server. Install it with: "
    "pip install git+https://github.com/adityakajaleyardi/Flatten.git"
)


@dataclass
class FileOutcome:
    """What happened to one document, in terms the report can print."""

    name: str
    status: str
    engine: str = ""
    detail: str = ""
    lost: float | None = None
    gained: float | None = None
    attempts: str = ""

    def as_row(self) -> dict[str, Any]:
        return {
            "File": self.name,
            "Status": self.status,
            "Engine": self.engine,
            "Detail": self.detail,
            "Content lost %": _percent(self.lost),
            "Content gained %": _percent(self.gained),
            "Engines tried": self.attempts,
        }


def build_runner(settings: FlattenSettings):
    """Return a job runner that flattens every PDF in the job's upload folder."""

    def execute(context: JobContext) -> dict[str, Any]:
        flatten_bytes, flatten_error = _load_library()
        options = settings.to_flatten_options()

        sources = sorted(
            path
            for path in context.uploads_dir.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf"
        )
        if not sources:
            raise ToolError("No PDFs were uploaded, so there is nothing to flatten.")

        total = len(sources)
        context.emit(
            Event(
                LEVEL_INFO,
                f"Flattening {total} PDF{'s' if total != 1 else ''} using the {settings.engine} engine...",
                total=total,
            )
        )

        outcomes: list[FileOutcome] = []
        for index, source in enumerate(sources, start=1):
            if context.cancel.is_set():
                break
            relative = source.relative_to(context.uploads_dir)
            outcome = _flatten_one(
                source=source,
                destination=context.output_dir / relative,
                name=relative.as_posix(),
                options=options,
                flatten_bytes=flatten_bytes,
                flatten_error=flatten_error,
            )
            outcomes.append(outcome)
            context.emit(_event_for(outcome, index, total))

        _write_report(context.output_dir / REPORT_NAME, outcomes)

        counts = dict.fromkeys((STATUS_FLATTENED, STATUS_REVIEW, STATUS_FAILED), 0)
        for outcome in outcomes:
            counts[outcome.status] += 1

        cancelled = context.cancel.is_set()
        context.emit(
            Event(
                LEVEL_INFO,
                f"Finished: {counts[STATUS_FLATTENED]} flattened, "
                f"{counts[STATUS_REVIEW]} need review, {counts[STATUS_FAILED]} failed.",
            )
        )

        return {
            "total": total,
            "flattened": counts[STATUS_FLATTENED],
            "review": counts[STATUS_REVIEW],
            "failed": counts[STATUS_FAILED],
            "skipped": total - len(outcomes),
            "cancelled": cancelled,
            "flagged": [
                {"name": outcome.name, "status": outcome.status, "detail": outcome.detail}
                for outcome in outcomes
                if outcome.status != STATUS_FLATTENED
            ],
        }

    return execute


def _load_library():
    """Import the library late, so a server without it can still serve the other tools."""
    try:
        from flatten_pdf import FlattenError, flatten_bytes
    except ImportError as error:  # pragma: no cover - depends on the install
        raise ToolError(INSTALL_HINT) from error
    return flatten_bytes, FlattenError


def _flatten_one(
    *,
    source: Path,
    destination: Path,
    name: str,
    options: Any,
    flatten_bytes: Any,
    flatten_error: type[Exception],
) -> FileOutcome:
    try:
        data = source.read_bytes()
    except OSError as error:
        return FileOutcome(name, STATUS_FAILED, detail=f"could not be read ({error.strerror})")

    try:
        flattened, result = flatten_bytes(data, options)
    except flatten_error as error:
        return FileOutcome(name, STATUS_FAILED, detail=str(error))
    except Exception as error:  # noqa: BLE001 - one bad file must not end the batch
        return FileOutcome(name, STATUS_FAILED, detail=f"unexpected error: {error}")

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(flattened)
    except OSError as error:
        return FileOutcome(
            name, STATUS_FAILED, engine=result.engine, detail=f"could not be saved ({error.strerror})"
        )

    return FileOutcome(
        name=name,
        status=STATUS_REVIEW if result.degraded else STATUS_FLATTENED,
        engine=result.engine,
        detail=result.verdict.reason if result.degraded else "",
        lost=result.verdict.lost,
        gained=result.verdict.gained,
        attempts="; ".join(result.explain()),
    )


def _event_for(outcome: FileOutcome, index: int, total: int) -> Event:
    if outcome.status == STATUS_FAILED:
        return Event(LEVEL_FAIL, f"{outcome.name}: {outcome.detail}", processed=index, total=total)
    if outcome.status == STATUS_REVIEW:
        return Event(
            LEVEL_WARNING,
            f"{outcome.name}: needs review, {outcome.detail} (best result from {outcome.engine})",
            processed=index,
            total=total,
        )
    return Event(LEVEL_OK, f"{outcome.name} ({outcome.engine})", processed=index, total=total)


def _write_report(path: Path, outcomes: list[FileOutcome]) -> None:
    """Write the per-file report that travels inside the download."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
            writer.writeheader()
            for outcome in outcomes:
                writer.writerow(outcome.as_row())
    except OSError:
        # The flattened files matter more than the report; losing it is survivable.
        pass


def _percent(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.2f}"
