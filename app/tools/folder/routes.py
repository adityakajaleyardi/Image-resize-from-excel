"""HTTP routes for the folder images tool."""

from __future__ import annotations

import zipfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...jobs import job_manager
from ...registry import get_tool
from ...templating import templates
from ...uploads import store_upload
from . import TOOL_ID
from .options import FIELD_DESCRIPTIONS, MODES, FolderSettings
from .runner import (
    PROPERTY_LIST_NAME,
    UNIT_MAPPING_NAME,
    UNIT_SUMMARY_NAME,
    build_runner,
)
from .settings import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    REPORT_NAME,
    load_default_options,
    save_default_options,
)

router = APIRouter()

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".ico")


@router.get("/folder")
async def run_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="folder/run.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "run",
            "tool": get_tool(TOOL_ID),
            "options": load_default_options(),
            "modes": MODES,
            "descriptions": FIELD_DESCRIPTIONS,
            "max_files": MAX_FILES,
            "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
            "max_total_mb": MAX_TOTAL_BYTES // (1024 * 1024),
        },
    )


@router.get("/folder/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="folder/help.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "help",
            "tool": get_tool(TOOL_ID),
            "modes": MODES,
            "descriptions": FIELD_DESCRIPTIONS,
        },
    )


@router.get("/api/folder/options/default")
async def get_default_options() -> dict:
    return load_default_options().to_dict()


@router.post("/api/folder/options/default")
async def set_default_options(payload: dict) -> dict:
    settings = _settings_from_mapping(payload)
    save_default_options(settings)
    return settings.to_dict()


@router.post("/api/folder/jobs")
async def create_job(
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(default=[]),
    unit_mapping: UploadFile | None = File(None),
    unit_summary: UploadFile | None = File(None),
    property_list: UploadFile | None = File(None),
    operation_mode: str = Form(""),
    max_file_size_mb: str = Form(""),
) -> dict:
    _require_available()

    settings = _settings_from_mapping(
        {"operation_mode": operation_mode, "max_file_size_mb": max_file_size_mb}
    )

    uploads = [upload for upload in files if upload.filename]
    if not uploads:
        raise HTTPException(status_code=400, detail="Choose a folder containing images.")
    if len(uploads) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=(f"{len(uploads)} files were selected. Please process at most {MAX_FILES} at a time."),
        )

    # Only trust the reported folder structure if there is one entry per file.
    relative_paths = list(paths) if len(paths) == len(uploads) else [""] * len(uploads)

    job = job_manager.create(TOOL_ID)
    # The outputs are JPEGs, so deflating them costs CPU and saves almost nothing.
    job.zip_compression = zipfile.ZIP_STORED

    try:
        total_bytes = 0
        pairs = zip(uploads, relative_paths, strict=True)
        for index, (upload, relative) in enumerate(pairs, start=1):
            # The library keys on everything below the folder the user picked.
            below_root = _strip_root(relative or upload.filename or "")
            if not below_root.lower().endswith(IMAGE_SUFFIXES):
                continue

            stored = await store_upload(
                upload,
                job.uploads_dir / "images",
                fallback_name=f"image-{index}.jpg",
                allowed_suffixes=IMAGE_SUFFIXES,
                max_bytes=MAX_FILE_BYTES,
                kind="an image",
                hint="Only image files can be processed.",
                relative_path=below_root,
            )
            total_bytes += stored.stat().st_size
            if total_bytes > MAX_TOTAL_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"The selection is larger than {MAX_TOTAL_BYTES // (1024 * 1024)} MB in "
                        "total. Please split it into smaller batches."
                    ),
                )

        for upload, name in (
            (unit_mapping, UNIT_MAPPING_NAME),
            (unit_summary, UNIT_SUMMARY_NAME),
            (property_list, PROPERTY_LIST_NAME),
        ):
            if upload is not None and upload.filename:
                await store_upload(
                    upload,
                    job.uploads_dir,
                    fallback_name=name,
                    allowed_suffixes=(".csv",),
                    max_bytes=MAX_FILE_BYTES,
                    kind="a CSV",
                    hint="The lookup files must be CSVs.",
                    # Stored under the expected name so the runner can find it,
                    # whatever the user's copy happens to be called.
                    relative_path=name,
                )
    except HTTPException:
        job_manager.delete(job.id)
        raise

    job.source_name = f"{len(uploads)} images"
    job.download_name = f"Processed_Images_{job.id[:8]}.zip"
    job.log_name = REPORT_NAME
    job_manager.submit(job, build_runner(settings))
    return {"id": job.id}


def _strip_root(reported_path: str) -> str:
    """Drop the top-level folder the user picked from a `webkitRelativePath`."""
    parts = [part for part in reported_path.replace("\\", "/").split("/") if part]
    return "/".join(parts[1:]) if len(parts) > 1 else "/".join(parts)


def _require_available() -> None:
    tool = get_tool(TOOL_ID)
    if not tool.available:
        raise HTTPException(
            status_code=503,
            detail=(
                "The image processing library is not installed on this server, so this tool "
                f"cannot run. Install it with: {tool.install_hint}"
            ),
        )


def _settings_from_mapping(payload: dict) -> FolderSettings:
    try:
        return FolderSettings.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
