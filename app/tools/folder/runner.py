"""The folder images run.

Reads the uploaded folder tree, hands it to the image-from-folder library one
image at a time, and writes each output straight to the job's output directory.
The library is imported inside the runner so a server without it still starts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ...events import Event, ToolError
from ...jobs import JobContext
from .options import FolderSettings
from .settings import REPORT_NAME

logger = logging.getLogger(__name__)

#: Uploaded under these names by the routes, and read back here.
UNIT_MAPPING_NAME = "UnitMapping.csv"
UNIT_SUMMARY_NAME = "CompanyUnitSummery.csv"
PROPERTY_LIST_NAME = "PropertyList-Property.csv"

_LEVELS = {"success": "ok", "skipped": "skip", "failed": "fail"}

# Pillow reports the in-memory buffer it was handed, which means nothing to a user.
_OBJECT_REPR = re.compile(r"\s*<[^<>]*object at 0x[0-9a-fA-F]+>")


class _Inputs:
    """The batch, read from disk one image at a time.

    A unit image fans out to one output per apartment, so a batch can be far
    larger in memory than on disk. Only `len` is needed up front, for progress.
    """

    def __init__(self, paths: list[Path], root: Path, build) -> None:
        self._paths = paths
        self._root = root
        self._build = build

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self):
        for path in self._paths:
            relative = path.relative_to(self._root).as_posix()
            yield self._build(relative, path.read_bytes())


def build_runner(settings: FolderSettings):
    def run(context: JobContext) -> dict[str, Any]:
        from image_from_folder import (
            InputImage,
            LookupData,
            ProcessResult,
            iter_process_images,
        )

        lookups = _build_lookups(context, LookupData)
        images_dir = context.uploads_dir / "images"
        paths = _collect(images_dir)

        inputs = _Inputs(paths, images_dir, InputImage.from_relative_path)
        total = len(inputs)
        context.emit(Event("info", f"Processing {total} images...", total=total))

        result = ProcessResult()
        written = 0

        for file_result in iter_process_images(inputs, lookups=lookups, config=settings.to_process_config()):
            result.results.append(file_result)
            result.outputs.extend(file_result.outputs)
            result.log.extend(file_result.log_entries)

            for output in file_result.outputs:
                # Two family linked properties can resolve to the same target.
                # Letting the later write win is what the original tool did.
                destination = context.output_dir / output.relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(output.data)
                written += 1

            context.emit(
                Event(
                    _LEVELS.get(file_result.status, "info"),
                    _describe(file_result),
                    processed=file_result.index,
                    total=total,
                )
            )

            if context.cancel.is_set():
                context.emit(Event("warning", "Cancelled. Keeping what was produced so far."))
                break

        (context.output_dir / REPORT_NAME).write_bytes(result.log_csv_bytes())

        return {
            "total": total,
            "succeeded": result.succeeded,
            "skipped": result.skipped,
            "failed": result.failed,
            "written": written,
        }

    return run


def _build_lookups(context: JobContext, lookup_data):
    """Cross reference data for unit images, or an empty set if none was given."""
    files = {
        "unit_mapping": context.uploads_dir / UNIT_MAPPING_NAME,
        "unit_summary": context.uploads_dir / UNIT_SUMMARY_NAME,
        "property_list": context.uploads_dir / PROPERTY_LIST_NAME,
    }
    present = {name: path for name, path in files.items() if path.exists()}

    if not present:
        return lookup_data.empty()

    missing = sorted(set(files) - set(present))
    if missing:
        raise ToolError(
            "Unit images need all three lookup files. Missing: "
            + ", ".join(files[name].name for name in missing)
            + "."
        )

    try:
        lookups = lookup_data.from_csv_bytes(**{name: path.read_bytes() for name, path in present.items()})
    except Exception as error:  # noqa: BLE001 - a bad CSV must reach the user, not the log
        raise ToolError(f"The lookup files could not be read: {error}") from error

    for warning in lookups.warnings:
        context.emit(Event("warning", f"Lookup data: {warning}"))
    return lookups


def _collect(images_dir: Path) -> list[Path]:
    """Every uploaded image filed as `<property>/<doc type>/<image>`."""
    if not images_dir.exists():
        raise ToolError("No images were uploaded.")

    paths = [
        path
        for path in sorted(images_dir.rglob("*"))
        if path.is_file() and not path.name.startswith(".") and len(path.relative_to(images_dir).parts) == 3
    ]
    if not paths:
        raise ToolError(
            "No images were filed as property code / document type / image, so there was nothing to process."
        )
    return paths


def _describe(file_result) -> str:
    """One log line for an image, saying why if nothing came of it."""
    name = f"{file_result.property_code}/{file_result.doc_type_folder}/{file_result.source_filename}"

    if file_result.status == "failed":
        error = _OBJECT_REPR.sub("", file_result.error or "").strip()
        return f"{name}: {error or 'could not be read'}"
    if file_result.status == "skipped":
        reason = "; ".join(file_result.skips) or "no matching units"
        return f"{name}: {reason}"

    count = len(file_result.outputs)
    return f"{name} -> {count} file{'' if count == 1 else 's'}"
