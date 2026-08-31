"""Settings that belong to the email converter alone."""

from __future__ import annotations

import json
from pathlib import Path

from ...settings import DATA_DIR
from . import TOOL_ID
from .options import EmailSettings

DEFAULT_OPTIONS_PATH = DATA_DIR / "emails_default_options.json"

#: Written into the output directory alongside the html and images folders.
FAILURE_LOG_NAME = "Failed_Records.csv"
HTML_DIR_NAME = "html"
IMAGE_DIR_NAME = "images"

#: What `read_table` accepts. Anything else is rejected before a job is created.
INPUT_SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls")

# One export holds thousands of compressed bodies, so the file itself is large
# even though it is only a table.
MAX_FILE_BYTES = 250 * 1024 * 1024

# Decoded emails carry resident names, addresses and lease details, so a run's
# workspace goes long before the server-wide retention would remove it.
RETENTION_HOURS = 2

# A run is measured in hours, so it queues in a lane of its own rather than
# holding one of the two shared workers the quick tools take turns on.
JOB_LANE = TOOL_ID


def load_default_options() -> EmailSettings:
    if DEFAULT_OPTIONS_PATH.exists():
        try:
            saved = json.loads(DEFAULT_OPTIONS_PATH.read_text(encoding="utf-8"))
            return EmailSettings.from_mapping(saved)
        except (OSError, ValueError):
            pass
    return EmailSettings()


def save_default_options(settings: EmailSettings) -> None:
    DEFAULT_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OPTIONS_PATH.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")


def renderer_path() -> Path | None:
    """Where wkhtmltoimage was found, or None if it is not installed.

    Screenshots shell out to it and it is not a pip package, so this is checked
    at startup and again when the run page is drawn. Decoding to HTML does not
    need it, which is why a missing binary disables screenshots rather than the
    whole tool.
    """
    try:
        from greystar_email_converter import RendererNotFoundError, find_wkhtmltoimage
    except ImportError:
        return None

    try:
        return find_wkhtmltoimage()
    except RendererNotFoundError:
        return None
