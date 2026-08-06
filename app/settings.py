"""Paths, limits and the saved default configuration.

Everything the server writes lives under `data/`, which is never committed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .processing.config import ProcessingConfig

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "samples"

DATA_DIR = Path(os.environ.get("IMAGE_PROCESSOR_DATA_DIR", BASE_DIR / "data"))
JOBS_DIR = DATA_DIR / "jobs"
DEFAULT_CONFIG_PATH = DATA_DIR / "default_config.json"

# Finished jobs are deleted after this long, so the host does not fill up.
JOB_RETENTION_HOURS = int(os.environ.get("IMAGE_PROCESSOR_JOB_RETENTION_HOURS", 24))

# Runs are network bound and long, so keep the queue short and predictable.
MAX_CONCURRENT_JOBS = int(os.environ.get("IMAGE_PROCESSOR_MAX_CONCURRENT_JOBS", 2))

MAX_UPLOAD_BYTES = 64 * 1024 * 1024

TEMPLATE_FILES = {
    "source": SAMPLES_DIR / "Source.csv",
    "property-map": SAMPLES_DIR / "PropertyHMY.csv",
    "config": SAMPLES_DIR / "Config.csv",
}


def ensure_directories() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def load_default_config() -> ProcessingConfig:
    """Return the saved default, seeding it on first run.

    A Config.csv left over from the desktop version is used as the seed so the
    operator's existing settings carry over.
    """
    if DEFAULT_CONFIG_PATH.exists():
        try:
            saved = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
            return ProcessingConfig.from_mapping(saved)
        except (OSError, ValueError):
            pass

    for seed in (BASE_DIR / "Config.csv", SAMPLES_DIR / "Config.csv"):
        if seed.exists():
            try:
                return ProcessingConfig.from_file(seed)
            except (OSError, ValueError):
                continue
    return ProcessingConfig()


def save_default_config(config: ProcessingConfig) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
