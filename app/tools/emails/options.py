"""The settings behind the email converter form.

`ColumnMapping` lives in the greystar-email-converter library, but the web layer
has to be importable on a server where that library is missing, and it needs
somewhere to put validation and the wording shown next to each field. So the
form is modelled here and converted to the library's own objects when a run
starts.

Rendering settings are deliberately absent. Zoom and the width rules are
calibrated against images that were produced before this app existed, so they
are left at the library's defaults and are not exposed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

LAYOUT_AUTO = "auto"
LAYOUT_CSV_EXPORT = "csv_export"
LAYOUT_LEGACY_XLSX = "legacy_xlsx"

#: The two layouts, duplicated from the library's `ColumnMapping` so the form can
#: name the columns without importing it. `tests/test_emails_options.py` fails if
#: the copy drifts from the original.
LAYOUT_COLUMNS = {
    LAYOUT_CSV_EXPORT: ("sBody", "hResEmailLog"),
    LAYOUT_LEGACY_XLSX: ("sEmailMessage", "hHistoryId"),
}

LAYOUTS = {
    LAYOUT_AUTO: "Detect from the file",
    LAYOUT_CSV_EXPORT: "CSV export ({} / {})".format(*LAYOUT_COLUMNS[LAYOUT_CSV_EXPORT]),
    LAYOUT_LEGACY_XLSX: "Legacy Excel ({} / {})".format(*LAYOUT_COLUMNS[LAYOUT_LEGACY_XLSX]),
}

FIELD_DESCRIPTIONS = {
    "column_layout": "Two column layouts are in circulation. Detecting reads the "
    "headings and picks the one that matches, which is safer than choosing by hand.",
    "render_images": "Screenshots take about a second each. Turning them off writes "
    "the HTML only, which is much faster and works without wkhtmltoimage installed.",
}


@dataclass(frozen=True)
class EmailSettings:
    column_layout: str = LAYOUT_AUTO
    render_images: bool = True

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> EmailSettings:
        defaults = cls()

        layout = str(payload.get("column_layout") or defaults.column_layout).strip()
        if layout not in LAYOUTS:
            raise ValueError(f"Column layout must be one of {sorted(LAYOUTS)}, not {layout!r}.")

        return cls(
            column_layout=layout,
            render_images=_as_bool(payload.get("render_images"), defaults.render_images, "Screenshots"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_column_mapping(self):
        """The library's own column mapping, or None when it is to be detected.

        Imported here rather than at module level so this module stays usable on
        a server where greystar-email-converter is not installed.
        """
        from greystar_email_converter import ColumnMapping

        if self.column_layout == LAYOUT_AUTO:
            return None
        if self.column_layout == LAYOUT_CSV_EXPORT:
            return ColumnMapping.csv_export()
        return ColumnMapping.legacy_xlsx()


def _as_bool(value: Any, default: bool, label: str) -> bool:
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "yes", "on", "1"):
        return True
    if text in ("false", "no", "off", "0"):
        return False
    raise ValueError(f'{label} must be true or false, not "{value}".')
