"""Background job management.

Tool agnostic. Each run gets its own workspace under `data/jobs/<id>/` so
concurrent users never share an output folder. Jobs are executed on a small
thread pool, report progress through an event log the browser polls, and are
packaged into a ZIP the user downloads. Workspaces are deleted once they expire.

A tool takes part by handing `submit` a runner: a callable that receives a
`JobContext` and returns a summary dictionary. The runner owns everything
specific to that tool, which is why nothing in this module imports a pipeline.

Two things a tool can ask for at submission time, both without naming itself
here: its own worker, so a run measured in hours cannot fill the shared queue,
and a retention window shorter than the default, for output too sensitive to sit
on disk for a day.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .events import Event, EventCallback, ToolError
from .settings import JOB_RETENTION_HOURS, JOBS_DIR, MAX_CONCURRENT_JOBS

logger = logging.getLogger(__name__)

RESULTS_ZIP_NAME = "results.zip"
EVENT_LOG_NAME = "events.jsonl"

# A shorter retention has to survive a restart, or a workspace nobody remembers
# creating would sit there for the default day instead. It is written into the
# workspace so the sweep can honour it without knowing which tool made the job.
RETENTION_MARKER_NAME = "retention-hours.txt"

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


@dataclass(frozen=True)
class JobContext:
    """Everything a runner is allowed to know about the job it is executing.

    Deliberately narrow: a runner reads uploads, writes to the output directory,
    emits events and honours the cancel flag. It never sees the job id, the
    workspace root or anything else it could leak into the interface.
    """

    uploads_dir: Path
    output_dir: Path
    emit: EventCallback
    cancel: threading.Event


#: Returns a summary to show the user once the run has finished.
Runner = Callable[[JobContext], dict[str, Any]]


@dataclass
class Job:
    id: str
    directory: Path
    created_at: datetime
    tool: str = ""
    #: Filename the browser is offered for the results ZIP.
    download_name: str = "results.zip"
    #: Report written into the output directory, offered as a separate download.
    log_name: str = ""
    source_name: str = ""
    #: Tools whose output is already compressed set this to ZIP_STORED.
    zip_compression: int = zipfile.ZIP_DEFLATED
    #: Overrides the server-wide retention. None means use the default.
    retention_hours: int | None = None
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

    @property
    def log_path(self) -> Path | None:
        if not self.log_name:
            return None
        candidate = self.output_dir / self.log_name
        return candidate if candidate.exists() else None

    def snapshot(self, since: int = 0) -> dict[str, Any]:
        """Status plus every event after `since`, for the browser to poll."""
        with self.lock:
            start = max(since - self.events_dropped, 0)
            new_events = self.events[start:]
            return {
                "id": self.id,
                "tool": self.tool,
                "status": self.status.value,
                "processed": self.processed,
                "total": self.total,
                "error": self.error,
                "summary": self.summary,
                "events": new_events,
                "cursor": self.events_dropped + len(self.events),
                "has_results": self.results_zip.exists(),
                "has_log": self.log_path is not None,
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
        # The shared pool is keyed None; a lane a tool asked for is keyed by name.
        self._executors: dict[str | None, ThreadPoolExecutor] = {}
        self._started = False
        self._shutdown = threading.Event()
        self._cleaner: threading.Thread | None = None

    def start(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._shutdown.clear()
        self._executors = {None: ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="job")}
        self._started = True
        self.cleanup_expired()
        self._cleaner = threading.Thread(target=self._cleanup_loop, name="job-cleanup", daemon=True)
        self._cleaner.start()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._started = False
        for job in self.all_jobs():
            job.cancel_event.set()
        for executor in self._executors.values():
            executor.shutdown(wait=False, cancel_futures=True)
        self._executors = {}

    def create(self, tool: str, *, retention_hours: int | None = None) -> Job:
        """Create an empty workspace ready to receive uploads."""
        job_id = uuid.uuid4().hex
        directory = self._jobs_dir / job_id
        (directory / "uploads").mkdir(parents=True, exist_ok=True)
        (directory / "output").mkdir(parents=True, exist_ok=True)

        if retention_hours is not None:
            (directory / RETENTION_MARKER_NAME).write_text(str(retention_hours), encoding="utf-8")

        job = Job(
            id=job_id,
            directory=directory,
            created_at=datetime.now(timezone.utc),
            tool=tool,
            retention_hours=retention_hours,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def submit(self, job: Job, runner: Runner, *, lane: str | None = None) -> None:
        """Queue a run, optionally in a lane of its own.

        A tool whose runs last hours passes a lane so it queues against itself
        rather than against the quick tools sharing the default pool.
        """
        if not self._started:
            self.start()
        self._executor_for(lane).submit(self._execute, job, runner)

    def _executor_for(self, lane: str | None) -> ThreadPoolExecutor:
        with self._lock:
            executor = self._executors.get(lane)
            if executor is None:
                # One worker: the point of a lane is isolation, not more capacity.
                executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"job-{lane}")
                self._executors[lane] = executor
            return executor

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
        self._append(job, Event("warning", "Cancelling after the current item..."))
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
        """Delete workspaces past their retention window, on disk and in memory."""
        now = time.time()
        removed = 0

        for job in self.all_jobs():
            if not job.status.is_finished:
                continue
            if job.created_at.timestamp() < now - self._seconds_for(job.retention_hours):
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
                if directory.stat().st_mtime < now - self._seconds_for(_marked_retention(directory)):
                    shutil.rmtree(directory, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
        return removed

    def _seconds_for(self, retention_hours: int | None) -> float:
        if retention_hours is None:
            return self._retention_seconds
        return retention_hours * 3600

    def _cleanup_loop(self) -> None:
        while not self._shutdown.wait(_CLEANUP_INTERVAL_SECONDS):
            try:
                self.cleanup_expired()
            except OSError:
                logger.exception("Job cleanup failed")

    def _execute(self, job: Job, runner: Runner) -> None:
        job.status = JobStatus.RUNNING
        context = JobContext(
            uploads_dir=job.uploads_dir,
            output_dir=job.output_dir,
            emit=lambda event: self._append(job, event),
            cancel=job.cancel_event,
        )
        try:
            job.summary = runner(context)
            self._package_results(job)
            job.status = JobStatus.CANCELLED if job.cancel_event.is_set() else JobStatus.COMPLETED
        except ToolError as error:
            job.status = JobStatus.FAILED
            job.error = str(error)
            self._append(job, Event("fail", str(error)))
        except Exception as error:  # noqa: BLE001 - a crash must still reach the user
            logger.exception("Job %s crashed", job.id)
            job.status = JobStatus.FAILED
            job.error = f"Unexpected error: {error}"
            self._append(job, Event("fail", job.error))

    def _package_results(self, job: Job) -> None:
        """Zip the output folder. Contents are already compressed, so keep it cheap."""
        files = [path for path in job.output_dir.rglob("*") if path.is_file()]
        if not files:
            return

        self._append(job, Event("info", f"Packaging {len(files)} files for download..."))
        deflating = job.zip_compression == zipfile.ZIP_DEFLATED
        try:
            with zipfile.ZipFile(
                job.results_zip,
                "w",
                compression=job.zip_compression,
                compresslevel=1 if deflating else None,
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


def _marked_retention(directory: Path) -> int | None:
    """The shorter retention a job asked for, if it left the marker behind."""
    try:
        return int((directory / RETENTION_MARKER_NAME).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


job_manager = JobManager()
