"""Shared paths and limits.

Everything the server writes lives under `data/`, which is never committed.
Settings that belong to one tool live in that tool's own `settings` module.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Shown in the header and the page titles. The project has not been renamed
#: yet, so keep this the single place that decides what the suite is called.
APP_NAME = "Internal Tools"

#: Environment variables are read as `<prefix>_<NAME>`. The old single-tool
#: names are still honoured so an existing deployment keeps working.
ENV_PREFIX = "TOOLKIT"
LEGACY_ENV_PREFIX = "IMAGE_PROCESSOR"


def env(name: str, default: str | None = None) -> str | None:
    for prefix in (ENV_PREFIX, LEGACY_ENV_PREFIX):
        value = os.environ.get(f"{prefix}_{name}")
        if value:
            return value
    return default


BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "samples"

DATA_DIR = Path(env("DATA_DIR") or BASE_DIR / "data")
JOBS_DIR = DATA_DIR / "jobs"

# Finished jobs are deleted after this long, so the host does not fill up.
JOB_RETENTION_HOURS = int(env("JOB_RETENTION_HOURS", "24"))

# Runs are long, so keep the queue short and predictable.
MAX_CONCURRENT_JOBS = int(env("MAX_CONCURRENT_JOBS", "2"))

#: Per-tool limits override this; it is the ceiling for anything that does not.
DEFAULT_MAX_UPLOAD_BYTES = 64 * 1024 * 1024


def ensure_directories() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
