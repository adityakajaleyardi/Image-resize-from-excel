"""HTTP routes for the PDF flatten tool."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...jobs import job_manager
from ...registry import get_tool
from ...templating import templates
from ...uploads import store_upload
from . import TOOL_ID
from .options import ENGINE_DESCRIPTIONS, ENGINES, FIELD_DESCRIPTIONS, FlattenSettings
from .runner import REPORT_COLUMNS, build_runner
from .settings import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    REPORT_NAME,
    load_default_options,
    save_default_options,
)

router = APIRouter()

PDF_SUFFIXES = (".pdf",)


@router.get("/flatten")
async def run_page(request: Request):
    tool = get_tool(TOOL_ID)
    return templates.TemplateResponse(
        request=request,
        name="flatten/run.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "run",
            "tool": tool,
            "options": load_default_options(),
            "engines": ENGINES,
            "engine_descriptions": ENGINE_DESCRIPTIONS,
            "descriptions": FIELD_DESCRIPTIONS,
            "max_files": MAX_FILES,
            "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
            "max_total_mb": MAX_TOTAL_BYTES // (1024 * 1024),
        },
    )


@router.get("/flatten/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="flatten/help.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "help",
            "tool": get_tool(TOOL_ID),
            "engines": ENGINES,
            "engine_descriptions": ENGINE_DESCRIPTIONS,
            "descriptions": FIELD_DESCRIPTIONS,
            "report_columns": REPORT_COLUMNS,
            "max_files": MAX_FILES,
            "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
            "max_total_mb": MAX_TOTAL_BYTES // (1024 * 1024),
        },
    )


@router.get("/api/flatten/options/default")
async def get_default_options() -> dict:
    return load_default_options().to_dict()


@router.post("/api/flatten/options/default")
async def set_default_options(payload: dict) -> dict:
    settings = _settings_from_mapping(payload)
    save_default_options(settings)
    return settings.to_dict()


@router.post("/api/flatten/jobs")
async def create_job(
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(default=[]),
    engine: str = Form("auto"),
    verify: str = Form("1"),
    verify_dpi: str = Form(""),
    tolerance: str = Form(""),
    allow_raster: str = Form("0"),
    raster_dpi: str = Form(""),
    flatten_annots: str = Form("1"),
) -> dict:
    _require_available()

    settings = _settings_from_mapping(
        {
            "engine": engine,
            "verify": verify,
            "verify_dpi": verify_dpi,
            "tolerance": tolerance,
            "allow_raster": allow_raster,
            "raster_dpi": raster_dpi,
            "flatten_annots": flatten_annots,
        }
    )

    uploads = [upload for upload in files if upload.filename]
    if not uploads:
        raise HTTPException(status_code=400, detail="Choose a folder containing at least one PDF.")
    if len(uploads) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"{len(uploads)} files were selected. Please flatten at most {MAX_FILES} at a time.",
        )

    # Only trust the reported folder structure if there is one entry per file.
    relative_paths = list(paths) if len(paths) == len(uploads) else [""] * len(uploads)

    job = job_manager.create(TOOL_ID)
    try:
        total_bytes = 0
        pairs = zip(uploads, relative_paths, strict=True)
        for index, (upload, relative) in enumerate(pairs, start=1):
            stored = await store_upload(
                upload,
                job.uploads_dir,
                fallback_name=f"document-{index}.pdf",
                allowed_suffixes=PDF_SUFFIXES,
                max_bytes=MAX_FILE_BYTES,
                kind="a PDF",
                hint="Only PDF files can be flattened.",
                relative_path=relative or upload.filename or "",
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
    except HTTPException:
        job_manager.delete(job.id)
        raise

    job.source_name = f"{len(uploads)} PDFs"
    job.download_name = f"Flattened_PDFs_{job.id[:8]}.zip"
    job.log_name = REPORT_NAME
    job_manager.submit(job, build_runner(settings))
    return {"id": job.id}


def _require_available() -> None:
    tool = get_tool(TOOL_ID)
    if not tool.available:
        raise HTTPException(
            status_code=503,
            detail=(
                "The PDF flattening library is not installed on this server, so this tool "
                f"cannot run. Install it with: {tool.install_hint}"
            ),
        )


def _settings_from_mapping(payload: dict) -> FlattenSettings:
    try:
        return FlattenSettings.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
