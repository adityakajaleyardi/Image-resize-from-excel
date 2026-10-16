"""Settings that belong to the image tool alone."""

from __future__ import annotations

import json

from ...processing.config import ProcessingConfig
from ...settings import BASE_DIR, DATA_DIR, SAMPLES_DIR

# Kept at the original name so a server that already has a saved default keeps it.
DEFAULT_CONFIG_PATH = DATA_DIR / "default_config.json"

# The uploads are CSV exports, which are small.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

TEMPLATE_FILES = {
    "source": SAMPLES_DIR / "Source.csv",
    "property-map": SAMPLES_DIR / "PropertyHMY.csv",
    "config": SAMPLES_DIR / "Config.csv",
}


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
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
