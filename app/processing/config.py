"""Run configuration.

`ProcessingConfig` is the single definition of what can be tuned per run. When a
setting is added here it also needs an entry in `FIELD_DESCRIPTIONS`, a control
in the web form, and a row in `samples/Config.csv`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping

from .constants import (
    OPERATION_MODE_RENAME_ONLY,
    OPERATION_MODE_RESIZE,
    PROPERTY_TYPE_LEGACY,
    PROPERTY_TYPE_MVC,
)
from .naming import clean_key

_TRUTHY = {"1", "yes", "true", "on", "y"}

# Shown as inline help next to each control in the web form.
FIELD_DESCRIPTIONS = {
    "sourcefile": "Name of the data file (command line only; the web app uses your upload).",
    "outputfolder": "Folder to save images into (command line only).",
    "operationmode": "1 = Rename only. 2 = Resize and rename.",
    "propertytype": "MVC or Legacy. Changes the target size used for some image types.",
    "manualsizing": "On = use the target width and height below. Off = size by image type.",
    "targetwidth": "Width in pixels, used only when manual sizing is on.",
    "targetheight": "Height in pixels, used only when manual sizing is on.",
    "maxfilesizemb": "Largest allowed file size. JPEGs are compressed until they fit.",
    "optimizedsuffix": "On = add 'Optimized' to the end of generated filenames.",
}

# The subset the web form exposes. Source file and output folder are decided by
# the upload and the job workspace, so they are not user editable there.
WEB_EDITABLE_FIELDS = (
    "operationmode",
    "propertytype",
    "manualsizing",
    "targetwidth",
    "targetheight",
    "maxfilesizemb",
    "optimizedsuffix",
)


@dataclass
class ProcessingConfig:
    sourcefile: str = "Source.csv"
    outputfolder: str = "Processed_Images"
    targetwidth: int = 2560
    targetheight: int = 1707
    maxfilesizemb: float = 1.0
    operationmode: int = OPERATION_MODE_RESIZE
    manualsizing: int = 0
    propertytype: str = PROPERTY_TYPE_MVC
    optimizedsuffix: int = 0

    def __post_init__(self) -> None:
        self.sourcefile = str(self.sourcefile).strip()
        self.outputfolder = str(self.outputfolder).strip()
        self.targetwidth = int(self.targetwidth)
        self.targetheight = int(self.targetheight)
        self.maxfilesizemb = float(self.maxfilesizemb)
        self.operationmode = int(self.operationmode)
        self.manualsizing = int(self.manualsizing)
        self.optimizedsuffix = int(self.optimizedsuffix)
        self.propertytype = str(self.propertytype).strip().upper()

        if self.operationmode not in (OPERATION_MODE_RENAME_ONLY, OPERATION_MODE_RESIZE):
            raise ValueError("Operation mode must be 1 (rename only) or 2 (resize and rename).")
        if self.propertytype not in (PROPERTY_TYPE_MVC, PROPERTY_TYPE_LEGACY):
            raise ValueError("Property type must be MVC or Legacy.")
        if self.targetwidth < 1 or self.targetheight < 1:
            raise ValueError("Target width and height must be at least 1 pixel.")
        if self.maxfilesizemb <= 0:
            raise ValueError("Max file size must be greater than zero.")

    @property
    def is_resize_mode(self) -> bool:
        return self.operationmode == OPERATION_MODE_RESIZE

    @property
    def uses_manual_sizing(self) -> bool:
        return self.manualsizing == 1

    @property
    def adds_optimized_suffix(self) -> bool:
        return self.optimizedsuffix == 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "ProcessingConfig":
        """Build a config from loosely named keys, ignoring anything unrecognised.

        Values that cannot be parsed fall back to the default for that field, so
        a partly corrupt config file still produces a usable run.
        """
        by_clean_key = {clean_key(f.name): f.name for f in fields(cls)}
        values: dict[str, Any] = {}

        for raw_key, raw_value in mapping.items():
            name = by_clean_key.get(clean_key(raw_key))
            if name is None:
                continue
            parsed = _parse_value(name, raw_value)
            if parsed is not None:
                values[name] = parsed

        return cls(**values)

    @classmethod
    def from_file(cls, path: Path) -> "ProcessingConfig":
        """Load from a two-column Config.csv or Config.xlsx (setting, value)."""
        import pandas as pd

        path = Path(path)
        if path.suffix.lower() in (".xlsx", ".xls"):
            frame = pd.read_excel(path, header=None)
        else:
            frame = pd.read_csv(path, header=None)

        mapping: dict[str, Any] = {}
        for _, row in frame.iterrows():
            if len(row) < 2 or pd.isna(row.iloc[0]):
                continue
            mapping[str(row.iloc[0])] = row.iloc[1]
        return cls.from_mapping(mapping)

    @classmethod
    def discover(cls, directory: Path) -> tuple["ProcessingConfig", Path | None]:
        """Find Config.xlsx or Config.csv in a directory, preferring the workbook.

        Returns the config and the file it came from, or the defaults and None.
        """
        for candidate in ("Config.xlsx", "Config.csv"):
            path = Path(directory) / candidate
            if path.exists():
                try:
                    return cls.from_file(path), path
                except (OSError, ValueError):
                    continue
        return cls(), None


def _parse_value(name: str, raw: Any) -> Any:
    """Coerce one raw config value, returning None when it is unusable."""
    import pandas as pd

    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return None

    text = str(raw).strip()
    if not text:
        return None

    if name in ("operationmode", "manualsizing", "optimizedsuffix"):
        try:
            return int(float(text))
        except ValueError:
            return 1 if text.lower() in _TRUTHY else 0
    if name in ("targetwidth", "targetheight"):
        try:
            return int(float(text))
        except ValueError:
            return None
    if name == "maxfilesizemb":
        try:
            return float(text)
        except ValueError:
            return None
    return text
