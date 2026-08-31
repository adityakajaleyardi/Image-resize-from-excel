"""The settings behind the folder images form.

`ProcessConfig` lives in the image-from-folder library, but the web layer has to
be importable on a server where that library is missing, and it needs somewhere
to put validation and the wording shown next to each field. So the form is
modelled here and converted to the library's own config when a run starts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MODE_RENAME_ONLY = 1
MODE_RESIZE_AND_RENAME = 2

MODES = {
    MODE_RESIZE_AND_RENAME: "Resize and rename",
    MODE_RENAME_ONLY: "Rename only",
}

FIELD_DESCRIPTIONS = {
    "operation_mode": "Resizing applies the dimension rule for each document type. "
    "Images are never scaled up.",
    "max_file_size_mb": "JPEG quality steps down to fit this, so it is a target rather than a guarantee.",
}

_SIZE_LIMITS = (0.1, 10.0)


@dataclass(frozen=True)
class FolderSettings:
    max_file_size_mb: float = 1.0
    operation_mode: int = MODE_RESIZE_AND_RENAME

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> FolderSettings:
        defaults = cls()

        mode = _as_int(payload.get("operation_mode"), defaults.operation_mode, "Operation")
        if mode not in MODES:
            raise ValueError(f"Operation must be one of {sorted(MODES)}, not {mode}.")

        size = _as_float(payload.get("max_file_size_mb"), defaults.max_file_size_mb, "Max file size")
        low, high = _SIZE_LIMITS
        if not low <= size <= high:
            raise ValueError(f"Max file size must be between {low} and {high} MB, not {size}.")

        return cls(max_file_size_mb=size, operation_mode=mode)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_process_config(self):
        """Convert to the library's own config object.

        Imported here rather than at module level so this module stays usable on
        a server where image-from-folder is not installed.
        """
        from image_from_folder import ProcessConfig

        return ProcessConfig(**self.to_dict())


def _as_int(value: Any, default: int, label: str) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label} must be a whole number, not "{value}".') from error


def _as_float(value: Any, default: float, label: str) -> float:
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label} must be a number, not "{value}".') from error
