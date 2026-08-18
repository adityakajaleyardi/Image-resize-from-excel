"""HTTP routes for the email converter."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ...jobs import job_manager
from ...registry import get_tool
from ...templating import templates
from ...uploads import store_upload
from . import TOOL_ID
from .options import FIELD_DESCRIPTIONS, LAYOUTS, EmailSettings
from .runner import build_runner
from .settings import (
    FAILURE_LOG_NAME,
    INPUT_SUFFIXES,
    JOB_LANE,
    MAX_FILE_BYTES,
    RETENTION_HOURS,
    load_default_options,
    renderer_path,
    save_default_options,
)

router = APIRouter()


@router.get("/emails")
async def run_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="emails/run.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "run",
            "tool": get_tool(TOOL_ID),
            "options": load_default_options(),
            "layouts": LAYOUTS,
            "descriptions": FIELD_DESCRIPTIONS,
            "can_render": renderer_path() is not None,
            "accepted": ", ".join(INPUT_SUFFIXES),
            "max_file_mb": MAX_FILE_BYTES // (1024 * 1024),
            "tool_retention_hours": RETENTION_HOURS,
        },
    )


@router.get("/emails/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="emails/help.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "help",
            "tool": get_tool(TOOL_ID),
            "layouts": LAYOUTS,
            "descriptions": FIELD_DESCRIPTIONS,
            "can_render": renderer_path() is not None,
            "tool_retention_hours": RETENTION_HOURS,
        },
    )


@router.get("/api/emails/options/default")
async def get_default_options() -> dict:
    return load_default_options().to_dict()


@router.post("/api/emails/options/default")
async def set_default_options(payload: dict) -> dict:
    settings = _settings_from_mapping(payload)
    save_default_options(settings)
    return settings.to_dict()


@router.post("/api/emails/jobs")
async def create_job(
    export: UploadFile = File(...),
    column_layout: str = Form(""),
    render_images: str = Form(""),
) -> dict:
    _require_available()

    settings = _settings_from_mapping({"column_layout": column_layout, "render_images": render_images})

    if settings.render_images and renderer_path() is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Screenshots are not available on this server because wkhtmltoimage is not "
                "installed. Turn screenshots off to convert to HTML only."
            ),
        )

    # Decoded output is personal data, so the workspace is removed hours before
    # the server-wide retention would get to it.
    job = job_manager.create(TOOL_ID, retention_hours=RETENTION_HOURS)

    try:
        await store_upload(
            export,
            job.uploads_dir,
            fallback_name="export.csv",
            allowed_suffixes=INPUT_SUFFIXES,
            max_bytes=MAX_FILE_BYTES,
            kind="a CSV or Excel file",
            hint=f"Accepted formats: {', '.join(INPUT_SUFFIXES)}.",
        )
    except HTTPException:
        job_manager.delete(job.id)
        raise

    job.source_name = export.filename or "export"
    job.download_name = f"Converted_Emails_{job.id[:8]}.zip"
    job.log_name = FAILURE_LOG_NAME
    # A long run queues against itself rather than filling the shared pool.
    job_manager.submit(job, build_runner(settings), lane=JOB_LANE)
    return {"id": job.id}


def _require_available() -> None:
    tool = get_tool(TOOL_ID)
    if not tool.available:
        raise HTTPException(
            status_code=503,
            detail=(
                "The email converter library is not installed on this server, so this tool "
                f"cannot run. Install it with: {tool.install_hint}"
            ),
        )


def _settings_from_mapping(payload: dict) -> EmailSettings:
    try:
        return EmailSettings.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
