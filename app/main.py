"""HTTP layer.

Assembles the tools and owns the endpoints they share: polling a job, cancelling
it and downloading what it produced. Everything tool specific lives under
`app.tools`, and all real work happens on the job thread pool.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .jobs import Job, job_manager
from .processing import ValidationError
from .registry import TOOLS, get_tool
from .settings import APP_NAME, ensure_directories
from .templating import APP_DIR, templates
from .tools.emails.routes import router as emails_router
from .tools.flatten.routes import router as flatten_router
from .tools.folder.routes import router as folder_router
from .tools.images.routes import router as images_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    job_manager.start()
    for tool in TOOLS:
        if not tool.available:
            logger.warning(
                "Tool %r is unavailable: %s is not installed. Install it with: %s",
                tool.id,
                tool.missing_requirement,
                tool.install_hint,
            )
    _check_screenshot_support()
    yield
    job_manager.shutdown()


def _check_screenshot_support() -> None:
    """Report at startup whether email screenshots can be produced.

    wkhtmltoimage is an executable rather than a pip package, so a server can
    have the library and still be unable to render. Decoding to HTML works
    without it, so this is reported rather than fatal, but it is reported here
    so it is found at deploy time and not by the first person to run a job.
    """
    if not get_tool("emails").available:
        return

    from .tools.emails.settings import renderer_path

    found = renderer_path()
    if found is None:
        logger.warning(
            "wkhtmltoimage was not found, so the email converter can only produce HTML. "
            "Install it from https://wkhtmltopdf.org/downloads.html, or set "
            "WKHTMLTOIMAGE_PATH to the executable."
        )
    else:
        logger.info("Email screenshots will use %s", found)


app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

app.include_router(images_router)
app.include_router(flatten_router)
app.include_router(folder_router)
app.include_router(emails_router)


@app.exception_handler(ValidationError)
async def _validation_error_handler(_: Request, error: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_tool": None,
            "active_page": "home",
        },
    )


@app.get("/help")
async def help_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="help.html",
        context={
            "active_tool": None,
            "active_page": "suite-help",
        },
    )


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
    return FileResponse(job.results_zip, media_type="application/zip", filename=job.download_name)


@app.get("/api/jobs/{job_id}/log")
async def download_log(job_id: str) -> FileResponse:
    job = _require_job(job_id)
    log_path = job.log_path
    if log_path is None:
        raise HTTPException(status_code=404, detail="No report was written for this run.")
    return FileResponse(log_path, media_type="text/csv", filename=job.log_name)


def _require_job(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="This run has expired or does not exist.")
    return job
