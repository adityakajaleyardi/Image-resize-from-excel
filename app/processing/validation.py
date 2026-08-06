"""Up front checks on uploaded CSVs.

Catching a missing column here means the user gets one clear message instead of
a job that runs for ten minutes and fails on every row.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Each entry lists the accepted spellings for one required column.
SOURCE_REQUIRED_COLUMNS: tuple[tuple[str, ...], ...] = (
    ("Property/Company Code", "Property Code"),
    ("File Name",),
    ("iType",),
    ("Doc. Type",),
    ("Active/Inactive",),
    ("Full Path",),
)

SOURCE_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "Property Name",
    "Order",
    "Floorplan Code",
    "Target Property",
    "Target Image Name",
)

# The property export misspells "Property", so both spellings are accepted.
HMY_CODE_COLUMNS = ("Propery Code", "Property Code")
HMY_ID_COLUMNS = ("Propery Id", "Property Id")

_ENCODINGS = ("utf-8-sig", "latin-1")


class ValidationError(Exception):
    """A user fixable problem with an uploaded file."""


def read_source_headers(path: Path) -> list[str]:
    """Read the source file's header row.

    The source export is read without a header so that the first row can be
    taken verbatim, which is also how the engine reads it.
    """
    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            frame = pd.read_csv(path, encoding=encoding, header=None, nrows=1, engine="python")
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error
            continue
        if frame.empty:
            raise ValidationError("The file is empty. Expected a header row followed by data rows.")
        return [str(value).strip() for value in frame.iloc[0]]

    raise ValidationError(f"The file could not be read as CSV: {last_error}")


def validate_source_csv(path: Path) -> list[str]:
    """Check a source file's header row, returning its columns.

    Raises ValidationError naming every missing column at once.
    """
    headers = read_source_headers(path)
    present = set(headers)

    missing = [
        alternatives for alternatives in SOURCE_REQUIRED_COLUMNS if not present.intersection(alternatives)
    ]
    if missing:
        described = ", ".join(" or ".join(f'"{name}"' for name in group) for group in missing)
        raise ValidationError(
            f"The source file is missing {len(missing)} required "
            f"column{'s' if len(missing) > 1 else ''}: {described}. "
            "Column names must match exactly, including spaces and full stops. "
            "Download the template from the Help page to compare."
        )
    return headers


def validate_property_hmy_csv(path: Path) -> tuple[str, str]:
    """Check a property mapping file, returning its (code, id) column names."""
    try:
        frame = pd.read_csv(path, nrows=1)
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise ValidationError(f"The property mapping file could not be read as CSV: {error}") from error

    headers = {str(column).strip() for column in frame.columns}
    code_column = next((name for name in HMY_CODE_COLUMNS if name in headers), None)
    id_column = next((name for name in HMY_ID_COLUMNS if name in headers), None)

    if code_column and id_column:
        return code_column, id_column

    missing = []
    if not code_column:
        missing.append(" or ".join(f'"{name}"' for name in HMY_CODE_COLUMNS))
    if not id_column:
        missing.append(" or ".join(f'"{name}"' for name in HMY_ID_COLUMNS))
    raise ValidationError(
        "The property mapping file is missing a required column: "
        + ", and ".join(missing)
        + ". Download the template from the Help page to compare."
    )
