"""The parts of the job layer every tool shares.

Focused on the two things a tool can ask for at submission time: a worker of its
own, and a retention window shorter than the server-wide one.
"""

from __future__ import annotations

import threading
import time

import pytest

from app.events import Event
from app.jobs import RETENTION_MARKER_NAME, JobManager, JobStatus


@pytest.fixture
def manager(tmp_path):
    instance = JobManager(jobs_dir=tmp_path / "jobs", max_workers=1, retention_hours=24)
    instance.start()
    yield instance
    instance.shutdown()


def finish(manager, job, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if job.status.is_finished:
            return job
        time.sleep(0.02)
    raise AssertionError("The job did not finish in time.")


class TestLanes:
    def test_a_job_without_a_lane_uses_the_shared_pool(self, manager):
        job = manager.create("images")
        manager.submit(job, lambda context: {"done": True})

        assert finish(manager, job).status is JobStatus.COMPLETED

    def test_a_lane_does_not_block_the_shared_pool(self, manager):
        """The point of a lane: a long run must not hold up the quick tools."""
        blocked = threading.Event()
        released = threading.Event()

        def slow(context):
            blocked.set()
            released.wait(timeout=5)
            return {}

        long_job = manager.create("emails")
        manager.submit(long_job, slow, lane="emails")
        assert blocked.wait(timeout=5), "the long run never started"

        # The shared pool has a single worker here, and it is still free.
        quick = manager.create("flatten")
        manager.submit(quick, lambda context: {"quick": True})
        finish(manager, quick)

        assert quick.status is JobStatus.COMPLETED
        assert long_job.status is JobStatus.RUNNING

        released.set()
        finish(manager, long_job)

    def test_two_runs_in_one_lane_queue_behind_each_other(self, manager):
        order: list[str] = []
        started_first = threading.Event()
        release_first = threading.Event()

        def first(context):
            started_first.set()
            release_first.wait(timeout=5)
            order.append("first")
            return {}

        one = manager.create("emails")
        two = manager.create("emails")
        manager.submit(one, first, lane="emails")
        assert started_first.wait(timeout=5)
        manager.submit(two, lambda context: order.append("second") or {}, lane="emails")

        assert two.status is JobStatus.QUEUED

        release_first.set()
        finish(manager, one)
        finish(manager, two)
        assert order == ["first", "second"]


class TestRetention:
    def test_a_job_keeps_the_server_wide_window_by_default(self, manager):
        assert manager.create("images").retention_hours is None

    def test_a_shorter_window_is_recorded_on_the_job(self, manager):
        job = manager.create("emails", retention_hours=2)

        assert job.retention_hours == 2

    def test_a_shorter_window_survives_a_restart(self, manager):
        job = manager.create("emails", retention_hours=2)

        assert (job.directory / RETENTION_MARKER_NAME).read_text(encoding="utf-8") == "2"

    def test_a_job_inside_its_window_is_kept(self, manager):
        job = manager.create("emails", retention_hours=2)
        manager.submit(job, lambda context: {})
        finish(manager, job)

        manager.cleanup_expired()

        assert manager.get(job.id) is not None

    def test_a_job_past_its_own_shorter_window_is_swept_up(self, manager):
        job = manager.create("emails", retention_hours=2)
        manager.submit(job, lambda context: {})
        finish(manager, job)
        _age(job, hours=3)

        manager.cleanup_expired()

        assert manager.get(job.id) is None
        assert not job.directory.exists()

    def test_the_same_age_is_fine_for_a_job_on_the_default_window(self, manager):
        job = manager.create("images")
        manager.submit(job, lambda context: {})
        finish(manager, job)
        _age(job, hours=3)

        manager.cleanup_expired()

        assert manager.get(job.id) is not None

    def test_a_running_job_is_never_swept_up(self, manager):
        job = manager.create("emails", retention_hours=2)
        job.status = JobStatus.RUNNING
        _age(job, hours=99)

        manager.cleanup_expired()

        assert manager.get(job.id) is not None

    def test_a_workspace_left_behind_by_a_restart_honours_its_marker(self, manager, tmp_path):
        orphan = tmp_path / "jobs" / "leftover"
        orphan.mkdir(parents=True)
        (orphan / RETENTION_MARKER_NAME).write_text("2", encoding="utf-8")
        _backdate(orphan, hours=3)

        manager.cleanup_expired()

        assert not orphan.exists()

    def test_an_unmarked_workspace_keeps_the_default_window(self, manager, tmp_path):
        orphan = tmp_path / "jobs" / "leftover"
        orphan.mkdir(parents=True)
        _backdate(orphan, hours=3)

        manager.cleanup_expired()

        assert orphan.exists()


class TestEvents:
    def test_progress_from_an_event_reaches_the_snapshot(self, manager):
        job = manager.create("emails", retention_hours=2)
        manager.submit(
            job,
            lambda context: context.emit(Event("ok", "one", processed=1, total=4)) or {},
        )
        finish(manager, job)

        snapshot = job.snapshot()
        assert snapshot["processed"] == 1
        assert snapshot["total"] == 4


def _age(job, *, hours: int) -> None:
    from datetime import timedelta

    job.created_at = job.created_at - timedelta(hours=hours)


def _backdate(directory, *, hours: int) -> None:
    import os

    old = time.time() - hours * 3600
    os.utime(directory, (old, old))
