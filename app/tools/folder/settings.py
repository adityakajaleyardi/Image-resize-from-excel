"""Settings that belong to the folder images tool alone."""

from __future__ import annotations

import json

from ...settings import DATA_DIR
from .options import FolderSettings

DEFAULT_OPTIONS_PATH = DATA_DIR / "folder_default_options.json"

REPORT_NAME = "Process_Log.csv"

# A batch is a folder of property images. Unit images fan out to one output per
# apartment, so the outgoing archive is far larger than what comes in; the caps
# are what stop one run filling the server's disk.
MAX_FILES = 2000
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024


def load_default_options() -> FolderSettings:
    if DEFAULT_OPTIONS_PATH.exists():
        try:
            saved = json.loads(DEFAULT_OPTIONS_PATH.read_text(encoding="utf-8"))
            return FolderSettings.from_mapping(saved)
        except (OSError, ValueError):
            pass
    return FolderSettings()


def save_default_options(settings: FolderSettings) -> None:
    DEFAULT_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OPTIONS_PATH.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
