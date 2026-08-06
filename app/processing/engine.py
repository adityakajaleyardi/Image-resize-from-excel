"""The processing run.

`run` downloads, resizes, renames and files every row of a source export. It
reports progress through an `on_event` callback rather than printing, so the web
app and the command line can both present it their own way.
"""

from __future__ import annotations

import os
import re
import threading
import urllib.parse
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from PIL import Image

from .config import ProcessingConfig
from .constants import (
    DOWNLOAD_TIMEOUT_SECONDS,
    FALLBACK_DOMAINS,
    PRIMARY_DOMAIN,
    get_target_box,
)
from .images import compress_and_save, resize_to_box
from .naming import build_auto_filename, clean_string, sanitise_target_image_name
from .validation import HMY_CODE_COLUMNS, HMY_ID_COLUMNS

LEVEL_INFO = "info"
LEVEL_OK = "ok"
LEVEL_SKIP = "skip"
LEVEL_WARNING = "warning"
LEVEL_FAIL = "fail"

PROCESS_LOG_NAME = "Process_Log.csv"
FAILED_LOG_STEM = "Failed_Log"

_SOURCE_ENCODINGS = ("utf-8-sig", "latin-1")
_P_CODE_PATH = re.compile(r"/dmslivecafe/2/\d+/")


class ProcessingError(Exception):
    """A run could not start or complete."""


@dataclass(frozen=True)
class Event:
    """One line of progress from a run."""

    level: str
    message: str
    row: int | None = None
    processed: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "row": self.row,
            "processed": self.processed,
            "total": self.total,
        }


@dataclass
class RunSummary:
    output_dir: Path
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: bool = False
    log_path: Path | None = None
    failed_log_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "cancelled": self.cancelled,
        }


EventCallback = Callable[[Event], None]


def run(
    config: ProcessingConfig,
    source_path: Path,
    hmy_path: Path | None = None,
    output_dir: Path | None = None,
    on_event: EventCallback | None = None,
    cancel: threading.Event | None = None,
) -> RunSummary:
    """Process every row of a source export into `output_dir`."""
    emit: EventCallback = on_event or (lambda event: None)
    cancel = cancel or threading.Event()

    source_path = Path(source_path)
    output_dir = Path(output_dir if output_dir is not None else config.outputfolder)

    if not source_path.exists():
        raise ProcessingError(f"Source file not found: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    for line in _describe_configuration(config):
        emit(Event(LEVEL_INFO, line))

    hmy_lookup = _load_property_ids(hmy_path, emit)
    frame = _read_source(source_path)

    summary = RunSummary(output_dir=output_dir, total=len(frame))
    emit(Event(LEVEL_INFO, f"Loaded {summary.total} rows from {source_path.name}.", total=summary.total))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    process_log: list[dict[str, Any]] = []
    failed_records: list[dict[str, Any]] = []
    processed = 0

    try:
        for _, row in frame.iterrows():
            if cancel.is_set():
                summary.cancelled = True
                emit(
                    Event(
                        LEVEL_WARNING,
                        "Cancelled. Files already written are kept.",
                        processed=processed,
                        total=summary.total,
                    )
                )
                break

            processed += 1
            outcome = _process_row(
                row=row,
                config=config,
                output_dir=output_dir,
                hmy_lookup=hmy_lookup,
                session=session,
            )

            if outcome.skipped:
                summary.skipped += 1
            elif outcome.error is None:
                summary.succeeded += 1
            else:
                summary.failed += 1
                failed_records.append(outcome.failed_record or {})

            if outcome.log_entry is not None:
                process_log.append(outcome.log_entry)

            emit(
                Event(
                    outcome.level,
                    outcome.message,
                    row=outcome.row,
                    processed=processed,
                    total=summary.total,
                )
            )
    finally:
        session.close()

    summary.log_path = _write_process_log(process_log, output_dir, emit)
    summary.failed_log_path = _write_failed_log(failed_records, output_dir, emit)
    return summary


@dataclass
class _RowOutcome:
    row: int
    level: str
    message: str
    skipped: bool = False
    error: str | None = None
    log_entry: dict[str, Any] | None = None
    failed_record: dict[str, Any] | None = None


def _process_row(
    *,
    row: pd.Series,
    config: ProcessingConfig,
    output_dir: Path,
    hmy_lookup: dict[str, str],
    session: requests.Session,
) -> _RowOutcome:
    row_index = int(row["RowIdx"])
    original_property = _text(row.get("Property/Company Code", row.get("Property Code", "")))
    target_property = _text(row.get("Target Property", "")) or original_property
    source_filename = _text(row.get("File Name", "")) or "Unknown"
    label = f"{original_property} -> {target_property} | {source_filename}"

    if _text(row.get("Active/Inactive", "")).upper() == "INACTIVE":
        return _RowOutcome(row_index, LEVEL_SKIP, f"{label} | Inactive record", skipped=True)

    doc_type = _text(row.get("Doc. Type", "")) or "Unknown"
    target_folder = output_dir / f"{clean_string(target_property)}__{clean_string(doc_type)}"
    raw_url = _text(row.get("Full Path", ""))

    try:
        target_folder.mkdir(parents=True, exist_ok=True)
        if not raw_url:
            raise ProcessingError("The Full Path column is empty, so there is nothing to download.")

        response = _download(session, _candidate_urls(raw_url, original_property, hmy_lookup))

        itype = _text(row.get("iType", "")) or "0"
        target_image_name = _text(row.get("Target Image Name", ""))
        save_format = _detect_format(itype, response.url, target_image_name)
        extension = ".png" if save_format == "PNG" else ".jpg"

        image = Image.open(BytesIO(response.content))
        image = image.convert("RGBA" if save_format == "PNG" else "RGB")

        action = "Kept original"
        if config.is_resize_mode:
            box = (
                (config.targetwidth, config.targetheight)
                if config.uses_manual_sizing
                else get_target_box(itype, config.propertytype)
            )
            if box:
                image, action = resize_to_box(image, box, config.uses_manual_sizing)

        if target_image_name:
            filename = sanitise_target_image_name(target_image_name, extension)
        else:
            filename = build_auto_filename(
                source_url=response.url,
                original_property=original_property,
                target_property=target_property,
                doc_type=doc_type,
                itype=itype,
                extension=extension,
                add_optimized_suffix=config.adds_optimized_suffix,
            )

        save_path = target_folder / filename
        size_mb = compress_and_save(image, save_path, config.maxfilesizemb, save_format)

        return _RowOutcome(
            row_index,
            LEVEL_OK,
            f"{label} | {action} | {size_mb:.2f} MB | {filename}",
            log_entry={
                "Folder": target_folder.name,
                "status": "success",
                "Original": raw_url,
                "New": str(save_path.relative_to(output_dir)),
                "SizeMB": round(size_mb, 2),
                "Error": "",
            },
        )

    except Exception as error:  # noqa: BLE001 - one bad row must not stop the run
        reason = str(error) or error.__class__.__name__
        failed_record = row.to_dict()
        failed_record["Error_Reason"] = reason
        return _RowOutcome(
            row_index,
            LEVEL_FAIL,
            f"{label} | {reason}",
            error=reason,
            log_entry={
                "Folder": target_folder.name,
                "status": "fail",
                "Original": raw_url,
                "New": "",
                "SizeMB": 0,
                "Error": reason,
            },
            failed_record=failed_record,
        )


def _describe_configuration(config: ProcessingConfig) -> list[str]:
    mode = "Resize and rename" if config.is_resize_mode else "Rename only"
    sizing = (
        f"Manual ({config.targetwidth}x{config.targetheight})"
        if config.uses_manual_sizing
        else "Automatic (by image type)"
    )
    return [
        f"Operation mode: {mode}",
        f"Property type: {config.propertytype}",
        f"Sizing: {sizing}",
        f"Max file size: {config.maxfilesizemb} MB",
        f"Optimized suffix: {'yes' if config.adds_optimized_suffix else 'no'}",
    ]


def _read_source(path: Path) -> pd.DataFrame:
    """Read a source export, taking its first row as the header.

    Adds a RowIdx column holding the spreadsheet line number, so log messages
    point at the row the user can actually see in Excel.
    """
    frame: pd.DataFrame | None = None
    last_error: Exception | None = None

    for encoding in _SOURCE_ENCODINGS:
        try:
            frame = pd.read_csv(path, encoding=encoding, header=None, engine="python")
            break
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error
        except pd.errors.EmptyDataError as error:
            raise ProcessingError("The source file is empty.") from error

    if frame is None:
        raise ProcessingError(f"The source file could not be read as CSV: {last_error}")
    if frame.empty:
        raise ProcessingError("The source file is empty.")

    frame.columns = [str(column).strip() for column in frame.iloc[0]]
    frame = frame.iloc[1:].copy()
    frame.insert(0, "RowIdx", frame.index + 1)
    return frame


def _load_property_ids(hmy_path: Path | None, emit: EventCallback) -> dict[str, str]:
    """Load the property code to property id mapping used for p-code URLs."""
    if hmy_path is None:
        return {}

    hmy_path = Path(hmy_path)
    if not hmy_path.exists():
        emit(
            Event(
                LEVEL_WARNING,
                f"Property mapping file not found: {hmy_path.name}. Continuing without it.",
            )
        )
        return {}

    try:
        frame = pd.read_csv(hmy_path)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        emit(
            Event(
                LEVEL_WARNING,
                f"Property mapping file could not be read ({error}). Continuing without it.",
            )
        )
        return {}

    frame.columns = [str(column).strip() for column in frame.columns]
    code_column = next((name for name in HMY_CODE_COLUMNS if name in frame.columns), None)
    id_column = next((name for name in HMY_ID_COLUMNS if name in frame.columns), None)

    if not code_column or not id_column:
        emit(
            Event(
                LEVEL_WARNING,
                "Property mapping file has no recognised code and id columns. Continuing without it.",
            )
        )
        return {}

    lookup = {
        _text(row[code_column]): _text(row[id_column])
        for _, row in frame.iterrows()
        if _text(row[code_column]) and _text(row[id_column])
    }
    emit(Event(LEVEL_INFO, f"Loaded {len(lookup)} property id mappings."))
    return lookup


def _candidate_urls(raw_url: str, property_code: str, hmy_lookup: dict[str, str]) -> list[str]:
    """Build the list of URLs to try, most likely first."""
    encoded = _safe_encode_url(raw_url)
    urls = [encoded]
    if property_code.lower().startswith("p") and property_code in hmy_lookup:
        urls.append(_P_CODE_PATH.sub(f"/dmslivecafe/3/{hmy_lookup[property_code]}/", encoded))
    return urls


def _download(session: requests.Session, urls: Sequence[str]) -> requests.Response:
    """Try each URL as given, then against the CDN fallback domains."""
    for url in urls:
        for candidate in _url_variants(url):
            try:
                response = session.get(candidate, timeout=DOWNLOAD_TIMEOUT_SECONDS)
            except requests.RequestException:
                continue
            if response.status_code == 200:
                return response
    raise ProcessingError("The file could not be downloaded. It returned an error or timed out.")


def _url_variants(url: str) -> Iterable[str]:
    """The URL itself, followed by the CDN mirrors of it where applicable."""
    yield url
    if PRIMARY_DOMAIN in url:
        for domain in FALLBACK_DOMAINS:
            yield url.replace(PRIMARY_DOMAIN, domain)


def _safe_encode_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path), parts.query, parts.fragment)
    )


def _detect_format(itype: str, resolved_url: str, target_image_name: str) -> str:
    """Decide the output format, preferring an extension the user asked for."""
    if target_image_name:
        extension = os.path.splitext(target_image_name)[1].lower()
        if extension == ".png":
            return "PNG"
        if extension in (".jpg", ".jpeg"):
            return "JPEG"

    if itype == "6":
        return "PNG"
    if itype in ("2", "40") and "png" in resolved_url.lower():
        return "PNG"
    return "JPEG"


def _text(value: Any) -> str:
    """Normalise a spreadsheet cell to a trimmed string, treating blanks as empty."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _write_process_log(entries: list[dict[str, Any]], output_dir: Path, emit: EventCallback) -> Path | None:
    if not entries:
        return None
    path = output_dir / PROCESS_LOG_NAME
    try:
        pd.DataFrame(entries).to_csv(path, index=False)
    except OSError as error:
        emit(Event(LEVEL_WARNING, f"Could not write the process log: {error}"))
        return None
    emit(Event(LEVEL_INFO, f"Saved process log: {path.name}"))
    return path


def _write_failed_log(records: list[dict[str, Any]], output_dir: Path, emit: EventCallback) -> Path | None:
    """Write failed rows as a workbook, falling back to CSV without openpyxl."""
    if not records:
        return None

    frame = pd.DataFrame(records)
    xlsx_path = output_dir / f"{FAILED_LOG_STEM}.xlsx"
    try:
        frame.to_excel(xlsx_path, index=False)
        emit(Event(LEVEL_INFO, f"Saved failed rows: {xlsx_path.name}"))
        return xlsx_path
    except (ImportError, ValueError, OSError):
        csv_path = output_dir / f"{FAILED_LOG_STEM}.csv"
        try:
            frame.to_csv(csv_path, index=False)
        except OSError as error:
            emit(Event(LEVEL_WARNING, f"Could not write the failed rows log: {error}"))
            return None
        emit(Event(LEVEL_INFO, f"Saved failed rows: {csv_path.name}"))
        return csv_path
