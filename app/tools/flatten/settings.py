"""Settings that belong to the flatten tool alone."""

from __future__ import annotations

import json

from ...settings import DATA_DIR
from .options import FlattenSettings

DEFAULT_OPTIONS_PATH = DATA_DIR / "flatten_default_options.json"

REPORT_NAME = "Flatten_Report.csv"

# A batch is meant to be a folder of maybe ten to twenty-five documents. The caps
# are generous enough not to get in the way, and low enough that one person
# cannot fill the server's disk by accident.
MAX_FILES = 100
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 300 * 1024 * 1024


def load_default_options() -> FlattenSettings:
    if DEFAULT_OPTIONS_PATH.exists():
        try:
            saved = json.loads(DEFAULT_OPTIONS_PATH.read_text(encoding="utf-8"))
            return FlattenSettings.from_mapping(saved)
        except (OSError, ValueError):
            pass
    return FlattenSettings()


def save_default_options(settings: FlattenSettings) -> None:
    DEFAULT_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OPTIONS_PATH.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
