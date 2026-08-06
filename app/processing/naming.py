"""Filename construction.

The rules here decide what processed files are called. Downstream systems match
on those names, so treat the output of `build_auto_filename` as a contract and
do not change it without an explicit request.
"""

from __future__ import annotations

import os
import re
import time
import urllib.parse

from .constants import DOC_TYPE_MAPPING, SHORTHAND_CHECK, UNKNOWN_DOC_TYPE_ABBREVIATION

# Characters Windows and POSIX both refuse in a filename.
_ILLEGAL_PATH_CHARS = re.compile(r'[/\\:*?"<>|]')


def clean_key(text: object) -> str:
    """Reduce a label to lowercase alphanumerics for forgiving key matching.

    Lets "Max File Size MB", "maxfilesizemb" and "Max_File_Size_MB" all resolve
    to the same configuration setting.
    """
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def clean_string(text: object) -> str:
    """Collapse anything that is not alphanumeric into single underscores."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "_", str(text))
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def get_filename_from_url(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url).path
        return os.path.basename(urllib.parse.unquote(path))
    except ValueError:
        return f"unknown_{int(time.time())}"


def get_doc_type_abbreviation(doc_type: object) -> str:
    return DOC_TYPE_MAPPING.get(str(doc_type).strip().upper(), UNKNOWN_DOC_TYPE_ABBREVIATION)


def describes_doc_type(original_name: str, abbreviation: str) -> bool:
    """True when the original filename already says what the doc type is."""
    keywords = SHORTHAND_CHECK.get(abbreviation, [abbreviation.lower()])
    normalised = original_name.lower().replace("_", "").replace(" ", "")
    return any(keyword.lower() in normalised for keyword in keywords)


def sanitise_target_image_name(name: str, fallback_extension: str) -> str:
    """Clean a user supplied filename, adding an extension only if it has none."""
    cleaned = _ILLEGAL_PATH_CHARS.sub("_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    _, extension = os.path.splitext(cleaned)
    return cleaned if extension else cleaned + fallback_extension


def build_auto_filename(
    *,
    source_url: str,
    original_property: str,
    target_property: str,
    doc_type: str,
    itype: str,
    extension: str,
    add_optimized_suffix: bool,
) -> str:
    """Build the generated name for an image with no Target Image Name."""
    url_filename = get_filename_from_url(source_url)
    name_without_extension = os.path.splitext(url_filename)[0]
    sanitised = clean_string(name_without_extension)

    clean_original = clean_string(original_property)
    # Exports often prefix the property code onto the filename. Strip it so the
    # target property is not followed by the original one.
    while clean_original and sanitised.lower().startswith(clean_original.lower()):
        sanitised = sanitised[len(clean_original) :].lstrip("_")

    parts = [clean_string(target_property), sanitised]

    itype = str(itype).strip()
    if itype and itype != "0" and itype.lower() not in sanitised.lower().split("_"):
        parts.append(itype)

    abbreviation = get_doc_type_abbreviation(doc_type)
    if abbreviation != UNKNOWN_DOC_TYPE_ABBREVIATION and not describes_doc_type(
        name_without_extension, abbreviation
    ):
        parts.append(abbreviation)

    if add_optimized_suffix:
        parts.append("Optimized")

    return "_".join(part for part in parts if part) + extension
