"""Background job management.

Each run gets its own workspace under `data/jobs/<id>/` so concurrent users
never share an output folder. Jobs are executed on a small thread pool, report
progress through an event log the browser polls, and are packaged into a ZIP the
user downloads. Workspaces are deleted once they expire.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .processing import ProcessingConfig, ProcessingError, run
from .processing.engine import Event
from .settings import JOB_RETENTION_HOURS, JOBS_DIR, MAX_CONCURRENT_JOBS

logger = logging.getLogger(__name__)

RESULTS_ZIP_NAME = "Processed_Images.zip"
EVENT_LOG_NAME = "events.jsonl"

# Keeping every event for a very large run would grow without bound. Older
# events are dropped once this many are held; the browser has already shown them.
MAX_EVENTS_RETAINED = 20_000

_CLEANUP_INTERVAL_SECONDS = 3600


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_finished(self) -> bool:
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


@dataclass
class Job:
    id: str
    directory: Path
    created_at: datetime
    source_name: str = ""
    status: JobStatus = JobStatus.QUEUED
    processed: int = 0
    total: int = 0
    error: str | None = None
    summary: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    events_dropped: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def uploads_dir(self) -> Path:
        return self.directory / "uploads"

    @property
    def output_dir(self) -> Path:
        return self.directory / "output"

    @property
    def results_zip(self) -> Path:
        return self.directory / RESULTS_ZIP_NAME

    def snapshot(self, since: int = 0) -> dict[str, Any]:
        """Status plus every event after `since`, for the browser to poll."""
        with self.lock:
            start = max(since - self.events_dropped, 0)
            new_events = self.events[start:]
            return {
                "id": self.id,
                "status": self.status.value,
                "processed": self.processed,
                "total": self.total,
                "error": self.error,
                "summary": self.summary,
                "events": new_events,
                "cursor": self.events_dropped + len(self.events),
                "has_results": self.results_zip.exists(),
                "finished": self.status.is_finished,
            }


class JobManager:
    """Owns job workspaces, the worker pool and expiry."""

    def __init__(
        self,
        jobs_dir: Path = JOBS_DIR,
        max_workers: int = MAX_CONCURRENT_JOBS,
        retention_hours: int = JOB_RETENTION_HOURS,
    ) -> None:
        self._jobs_dir = Path(jobs_dir)
        self._retention_seconds = retention_hours * 3600
        self._max_workers = max_workers
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        # Created on start rather than here, so the manager can be started again
        # after a shutdown. A pool that has been shut down cannot be reused.
        self._executor: ThreadPoolExecutor | None = None
        self._shutdown = threading.Event()
        self._cleaner: threading.Thread | None = None

    def start(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._shutdown.clear()
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="job")
        self.cleanup_expired()
        self._cleaner = threading.Thread(target=self._cleanup_loop, name="job-cleanup", daemon=True)
        self._cleaner.start()

    def shutdown(self) -> None:
        self._shutdown.set()
        for job in self.all_jobs():
            job.cancel_event.set()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def create(self) -> Job:
        """Create an empty workspace ready to receive uploads."""
        job_id = uuid.uuid4().hex
        directory = self._jobs_dir / job_id
        (directory / "uploads").mkdir(parents=True, exist_ok=True)
        (directory / "output").mkdir(parents=True, exist_ok=True)

        job = Job(id=job_id, directory=directory, created_at=datetime.now(timezone.utc))
        with self._lock:
            self._jobs[job_id] = job
        return job

    def submit(
        self,
        job: Job,
        config: ProcessingConfig,
        source_path: Path,
        hmy_path: Path | None,
    ) -> None:
        if self._executor is None:
            self.start()
        job.source_name = source_path.name
        self._executor.submit(self._execute, job, config, source_path, hmy_path)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.status.is_finished:
            return False
        job.cancel_event.set()
        self._append(job, Event("warning", "Cancelling after the current image..."))
        return True

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        job.cancel_event.set()
        shutil.rmtree(job.directory, ignore_errors=True)
        return True

    def cleanup_expired(self) -> int:
        """Delete workspaces past the retention window, on disk and in memory."""
        cutoff = time.time() - self._retention_seconds
        removed = 0

        for job in self.all_jobs():
            if job.created_at.timestamp() < cutoff and job.status.is_finished:
                self.delete(job.id)
                removed += 1

        if not self._jobs_dir.exists():
            return removed

        known = {job.id for job in self.all_jobs()}
        for directory in self._jobs_dir.iterdir():
            # Directories with no job in memory are left over from a previous run.
            if not directory.is_dir() or directory.name in known:
                continue
            try:
                if directory.stat().st_mtime < cutoff:
                    shutil.rmtree(directory, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
        return removed

    def _cleanup_loop(self) -> None:
        while not self._shutdown.wait(_CLEANUP_INTERVAL_SECONDS):
            try:
                self.cleanup_expired()
            except OSError:
                logger.exception("Job cleanup failed")

    def _execute(
        self,
        job: Job,
        config: ProcessingConfig,
        source_path: Path,
        hmy_path: Path | None,
    ) -> None:
        job.status = JobStatus.RUNNING
        try:
            summary = run(
                config=config,
                source_path=source_path,
                hmy_path=hmy_path,
                output_dir=job.output_dir,
                on_event=lambda event: self._append(job, event),
                cancel=job.cancel_event,
            )
            job.summary = summary.to_dict()
            self._package_results(job)
            job.status = JobStatus.CANCELLED if summary.cancelled else JobStatus.COMPLETED
            self._append(
                job,
                Event(
                    "info",
                    f"Finished: {summary.succeeded} processed, {summary.failed} failed, "
                    f"{summary.skipped} skipped.",
                ),
            )
        except ProcessingError as error:
            job.status = JobStatus.FAILED
            job.error = str(error)
            self._append(job, Event("fail", str(error)))
        except Exception as error:  # noqa: BLE001 - a crash must still reach the user
            logger.exception("Job %s crashed", job.id)
            job.status = JobStatus.FAILED
            job.error = f"Unexpected error: {error}"
            self._append(job, Event("fail", job.error))

    def _package_results(self, job: Job) -> None:
        """Zip the output folder. Images are already compressed, so keep it cheap."""
        files = [path for path in job.output_dir.rglob("*") if path.is_file()]
        if not files:
            return

        self._append(job, Event("info", f"Packaging {len(files)} files for download..."))
        try:
            with zipfile.ZipFile(
                job.results_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
            ) as archive:
                for path in files:
                    archive.write(path, path.relative_to(job.output_dir))
        except OSError as error:
            self._append(job, Event("warning", f"Could not build the download: {error}"))

    def _append(self, job: Job, event: Event) -> None:
        payload = event.to_dict()
        with job.lock:
            job.events.append(payload)
            if event.total:
                job.total = event.total
            if event.processed:
                job.processed = event.processed
            overflow = len(job.events) - MAX_EVENTS_RETAINED
            if overflow > 0:
                del job.events[:overflow]
                job.events_dropped += overflow

        try:
            with (job.directory / EVENT_LOG_NAME).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        except OSError:
            pass


job_manager = JobManager()
