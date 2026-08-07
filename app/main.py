"""HTTP layer.

Assembles the tools and owns the endpoints they share: polling a job, cancelling
it and downloading what it produced. Everything tool specific lives under
`app.tools`, and all real work happens on the job thread pool.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .jobs import Job, job_manager
from .processing import ValidationError
from .registry import TOOLS
from .settings import APP_NAME, ensure_directories
from .templating import APP_DIR
from .tools.flatten.routes import router as flatten_router
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
    yield
    job_manager.shutdown()


app = FastAPI(title=APP_NAME, version=__version__, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

app.include_router(images_router)
app.include_router(flatten_router)


@app.exception_handler(ValidationError)
async def _validation_error_handler(_: Request, error: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.get("/")
async def home() -> RedirectResponse:
    return RedirectResponse(url=TOOLS[0].path)


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
