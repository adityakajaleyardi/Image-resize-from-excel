"""HTTP routes for the image tool."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ...events import Event
from ...jobs import JobContext, job_manager
from ...processing import ProcessingConfig, ValidationError, run
from ...processing.config import FIELD_DESCRIPTIONS, WEB_EDITABLE_FIELDS
from ...processing.constants import DOC_TYPE_MAPPING, describe_allowed_hosts
from ...processing.engine import PROCESS_LOG_NAME
from ...processing.validation import (
    HMY_CODE_COLUMNS,
    HMY_ID_COLUMNS,
    SOURCE_OPTIONAL_COLUMNS,
    SOURCE_REQUIRED_COLUMNS,
    validate_property_hmy_csv,
    validate_source_csv,
)
from ...templating import templates
from ...uploads import store_upload
from . import TOOL_ID
from .settings import (
    MAX_UPLOAD_BYTES,
    TEMPLATE_FILES,
    load_default_config,
    save_default_config,
)

router = APIRouter()

CSV_SUFFIXES = (".csv",)


@router.get("/images")
async def run_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="images/run.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "run",
            "config": load_default_config(),
            "descriptions": FIELD_DESCRIPTIONS,
            "editable_fields": WEB_EDITABLE_FIELDS,
        },
    )


@router.get("/images/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="images/help.html",
        context={
            "active_tool": TOOL_ID,
            "active_page": "help",
            "required_columns": SOURCE_REQUIRED_COLUMNS,
            "optional_columns": SOURCE_OPTIONAL_COLUMNS,
            "hmy_code_columns": HMY_CODE_COLUMNS,
            "hmy_id_columns": HMY_ID_COLUMNS,
            "doc_types": sorted(DOC_TYPE_MAPPING.items()),
            "allowed_hosts": describe_allowed_hosts(),
        },
    )


@router.get("/api/images/config/default")
async def get_default_config() -> dict:
    return load_default_config().to_dict()


@router.post("/api/images/config/default")
async def set_default_config(payload: dict) -> dict:
    config = _config_from_mapping(payload)
    save_default_config(config)
    return config.to_dict()


@router.post("/api/images/jobs")
async def create_job(
    source: UploadFile = File(...),
    property_map: UploadFile | None = File(None),
    operationmode: str = Form(...),
    propertytype: str = Form(...),
    manualsizing: str = Form("0"),
    targetwidth: str = Form(...),
    targetheight: str = Form(...),
    maxfilesizemb: str = Form(...),
    optimizedsuffix: str = Form("0"),
) -> dict:
    config = _config_from_mapping(
        {
            "operationmode": operationmode,
            "propertytype": propertytype,
            "manualsizing": manualsizing,
            "targetwidth": targetwidth,
            "targetheight": targetheight,
            "maxfilesizemb": maxfilesizemb,
            "optimizedsuffix": optimizedsuffix,
        }
    )

    job = job_manager.create(TOOL_ID)
    try:
        source_path = await _store_csv(source, job.uploads_dir, "Source.csv")
        validate_source_csv(source_path)

        hmy_path = None
        if property_map is not None and property_map.filename:
            hmy_path = await _store_csv(property_map, job.uploads_dir, "PropertyHMY.csv")
            validate_property_hmy_csv(hmy_path)
    except (ValidationError, HTTPException):
        job_manager.delete(job.id)
        raise

    job.source_name = source_path.name
    job.download_name = f"Processed_Images_{job.id[:8]}.zip"
    job.log_name = PROCESS_LOG_NAME
    job_manager.submit(job, _runner(config, source_path, hmy_path))
    return {"id": job.id}


@router.get("/api/images/templates/{name}")
async def download_template(name: str) -> FileResponse:
    path = TEMPLATE_FILES.get(name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Unknown template.")
    return FileResponse(path, media_type="text/csv", filename=path.name)


def _runner(config: ProcessingConfig, source_path: Path, hmy_path: Path | None):
    def execute(context: JobContext) -> dict:
        summary = run(
            config=config,
            source_path=source_path,
            hmy_path=hmy_path,
            output_dir=context.output_dir,
            on_event=context.emit,
            cancel=context.cancel,
        )
        context.emit(
            Event(
                "info",
                f"Finished: {summary.succeeded} processed, {summary.failed} failed, "
                f"{summary.skipped} skipped.",
            )
        )
        return summary.to_dict()

    return execute


def _config_from_mapping(payload: dict) -> ProcessingConfig:
    try:
        return ProcessingConfig.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _store_csv(upload: UploadFile, directory: Path, fallback_name: str) -> Path:
    return await store_upload(
        upload,
        directory,
        fallback_name=fallback_name,
        allowed_suffixes=CSV_SUFFIXES,
        max_bytes=MAX_UPLOAD_BYTES,
        kind="a CSV file",
        hint="In Excel use File, Save As, and choose CSV.",
    )
