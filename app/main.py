"""HTTP layer.

Serves the single page front end and the small JSON API behind it. All real work
happens in `app.jobs` and `app.processing`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .jobs import Job, job_manager
from .processing import ProcessingConfig, ValidationError
from .processing.config import FIELD_DESCRIPTIONS, WEB_EDITABLE_FIELDS
from .processing.constants import DOC_TYPE_MAPPING
from .processing.engine import PROCESS_LOG_NAME
from .processing.validation import (
    HMY_CODE_COLUMNS,
    HMY_ID_COLUMNS,
    SOURCE_OPTIONAL_COLUMNS,
    SOURCE_REQUIRED_COLUMNS,
    validate_property_hmy_csv,
    validate_source_csv,
)
from .settings import (
    MAX_UPLOAD_BYTES,
    TEMPLATE_FILES,
    ensure_directories,
    load_default_config,
    save_default_config,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
UPLOAD_CHUNK_BYTES = 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    job_manager.start()
    yield
    job_manager.shutdown()


app = FastAPI(title="Image Processor", version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.exception_handler(ValidationError)
async def _validation_error_handler(_: Request, error: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.get("/")
async def index(request: Request):
    config = load_default_config()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "active_page": "run",
            "config": config,
            "descriptions": FIELD_DESCRIPTIONS,
            "editable_fields": WEB_EDITABLE_FIELDS,
            "version": __version__,
        },
    )


@app.get("/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="help.html",
        context={
            "active_page": "help",
            "required_columns": SOURCE_REQUIRED_COLUMNS,
            "optional_columns": SOURCE_OPTIONAL_COLUMNS,
            "hmy_code_columns": HMY_CODE_COLUMNS,
            "hmy_id_columns": HMY_ID_COLUMNS,
            "doc_types": sorted(DOC_TYPE_MAPPING.items()),
            "version": __version__,
        },
    )


@app.get("/api/config/default")
async def get_default_config() -> dict:
    return load_default_config().to_dict()


@app.post("/api/config/default")
async def set_default_config(payload: dict) -> dict:
    config = _config_from_mapping(payload)
    save_default_config(config)
    return config.to_dict()


@app.post("/api/jobs")
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

    job = job_manager.create()
    try:
        source_path = await _store_upload(source, job.uploads_dir, "Source.csv")
        validate_source_csv(source_path)

        hmy_path = None
        if property_map is not None and property_map.filename:
            hmy_path = await _store_upload(property_map, job.uploads_dir, "PropertyHMY.csv")
            validate_property_hmy_csv(hmy_path)
    except (ValidationError, HTTPException):
        job_manager.delete(job.id)
        raise

    job_manager.submit(job, config, source_path, hmy_path)
    return {"id": job.id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, cursor: int = Query(0, ge=0)) -> dict:
    return _require_job(job_id).snapshot(since=cursor)


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    _require_job(job_id)
    return {"cancelled": job_manager.cancel(job_id)}


@app.get("/api/jobs/{job_id}/download")
async def download_results(job_id: str) -> FileResponse:
    job = _require_job(job_id)
    if not job.results_zip.exists():
        raise HTTPException(status_code=404, detail="This run produced no files to download.")
    return FileResponse(
        job.results_zip,
        media_type="application/zip",
        filename=f"Processed_Images_{job.id[:8]}.zip",
    )


@app.get("/api/jobs/{job_id}/log")
async def download_log(job_id: str) -> FileResponse:
    job = _require_job(job_id)
    log_path = job.output_dir / PROCESS_LOG_NAME
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="No process log was written for this run.")
    return FileResponse(log_path, media_type="text/csv", filename=PROCESS_LOG_NAME)


@app.get("/api/templates/{name}")
async def download_template(name: str) -> FileResponse:
    path = TEMPLATE_FILES.get(name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Unknown template.")
    return FileResponse(path, media_type="text/csv", filename=path.name)


def _require_job(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="This run has expired or does not exist.")
    return job


def _config_from_mapping(payload: dict) -> ProcessingConfig:
    try:
        return ProcessingConfig.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _store_upload(upload: UploadFile, directory: Path, fallback_name: str) -> Path:
    """Stream an upload to disk, rejecting anything that is not a reasonable CSV."""
    name = Path(upload.filename or fallback_name).name or fallback_name
    if not name.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail=f'"{name}" is not a CSV file. In Excel use File, Save As, and choose CSV.',
        )

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    written = 0

    with destination.open("wb") as handle:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"{name} is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                )
            handle.write(chunk)

    if written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{name} is empty.")

    return destination
