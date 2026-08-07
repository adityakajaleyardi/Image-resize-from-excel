"""The settings behind the flatten form.

`FlattenOptions` lives in the flatten-pdf library, but the web layer needs to be
importable on a server where that library is missing, and it needs somewhere to
put validation and the wording shown next to each field. So the form is modelled
here and converted to the library's own options only when a run actually starts.

The defaults mirror the library's. `tests/test_flatten_options.py` fails if the
two ever drift apart.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

ENGINES = ("auto", "bake", "stamp", "raster")

ENGINE_DESCRIPTIONS = {
    "auto": "Try each engine in turn and keep the first result that verifies. Recommended.",
    "bake": "PyMuPDF's native flattening. Fast, and right for most files.",
    "stamp": "Draw each annotation into the page content. Handles files bake cannot.",
    "raster": "Render every page to an image. Always looks right, but the text is no "
    "longer selectable or searchable.",
}

FIELD_DESCRIPTIONS = {
    "engine": "Which flattening technique to use.",
    "verify": "Re-render every page and compare it against the original, so a file that "
    "lost content is reported instead of quietly handed back.",
    "verify_dpi": "Resolution used for that comparison. Higher is stricter and slower.",
    "tolerance": "How much of the original ink a page may lose before the result is "
    "treated as suspect. 0.005 is half a percent.",
    "allow_raster": "Let the automatic chain fall back to rasterising when nothing else "
    "verifies. The output stops being searchable, so it is off by default.",
    "raster_dpi": "Resolution used when a page is rasterised.",
    "flatten_annots": "Also flatten comments, stamps and other annotations, not just form "
    "fields. Links stay clickable either way.",
}

_LIMITS = {
    "verify_dpi": (36, 300),
    "raster_dpi": (72, 600),
    "tolerance": (0.0, 0.5),
}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class FlattenSettings:
    engine: str = "auto"
    verify: bool = True
    verify_dpi: int = 72
    tolerance: float = 0.005
    allow_raster: bool = False
    raster_dpi: int = 150
    flatten_annots: bool = True

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> FlattenSettings:
        defaults = cls()
        engine = str(payload.get("engine", defaults.engine)).strip().lower() or defaults.engine
        if engine not in ENGINES:
            raise ValueError(f'Engine must be one of {", ".join(ENGINES)}, not "{engine}".')

        settings = cls(
            engine=engine,
            verify=_as_bool(payload.get("verify"), defaults.verify, "Verify"),
            verify_dpi=_as_int(payload.get("verify_dpi"), defaults.verify_dpi, "Verification DPI"),
            tolerance=_as_float(payload.get("tolerance"), defaults.tolerance, "Tolerance"),
            allow_raster=_as_bool(payload.get("allow_raster"), defaults.allow_raster, "Allow raster"),
            raster_dpi=_as_int(payload.get("raster_dpi"), defaults.raster_dpi, "Raster DPI"),
            flatten_annots=_as_bool(
                payload.get("flatten_annots"), defaults.flatten_annots, "Flatten annotations"
            ),
        )

        for field_name, (low, high) in _LIMITS.items():
            value = getattr(settings, field_name)
            if not low <= value <= high:
                label = field_name.replace("_", " ").capitalize()
                raise ValueError(f"{label} must be between {low} and {high}, not {value}.")

        return settings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_flatten_options(self):
        """Convert to the library's own options object.

        Imported here rather than at module level so this module stays usable on a
        server where flatten-pdf is not installed.
        """
        from flatten_pdf import FlattenOptions

        return FlattenOptions(**self.to_dict())


def _as_bool(value: Any, default: bool, label: str) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f'{label} must be yes or no, not "{value}".')


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
