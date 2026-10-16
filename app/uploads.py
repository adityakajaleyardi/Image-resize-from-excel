"""Receiving uploads without trusting anything the browser says about them.

Filenames arrive from the client, so they are treated as hostile: a name may not
escape the job workspace, may not contain characters Windows refuses, and may not
be longer than the file system will take.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_CHUNK_BYTES = 1024 * 1024

_SEPARATORS = re.compile(r"[\\/]+")
# Reserved on Windows, plus control characters.
_UNSAFE = re.compile(r'[<>:"|?*\x00-\x1f]')
_MAX_PART_LENGTH = 120
_MAX_DEPTH = 12


def safe_name(raw: str, fallback: str) -> str:
    """A single path component that is safe to create on any platform."""
    cleaned = _UNSAFE.sub("_", Path(_SEPARATORS.split(raw or "")[-1]).name).strip(" .")
    if len(cleaned) > _MAX_PART_LENGTH:
        stem, dot, suffix = cleaned.rpartition(".")
        keep = _MAX_PART_LENGTH - len(suffix) - 1
        cleaned = f"{stem[:keep]}{dot}{suffix}" if dot else cleaned[:_MAX_PART_LENGTH]
    return cleaned or fallback


def safe_relative_path(raw: str, fallback: str) -> Path:
    """A relative path from the browser that cannot climb out of its directory.

    `webkitdirectory` reports paths like `Invoices/2024/march.pdf`. The structure
    is worth keeping in the download, but every component still has to be cleaned
    and `..` has to go.
    """
    parts: list[str] = []
    for part in _SEPARATORS.split(raw or ""):
        part = part.strip()
        if not part or part in (".", "..") or part.endswith(":"):
            continue
        cleaned = safe_name(part, "")
        if cleaned:
            parts.append(cleaned)

    if not parts:
        return Path(fallback)
    return Path(*parts[-_MAX_DEPTH:])


async def store_upload(
    upload: UploadFile,
    directory: Path,
    *,
    fallback_name: str,
    allowed_suffixes: tuple[str, ...],
    max_bytes: int,
    kind: str,
    hint: str = "",
    relative_path: str | None = None,
) -> Path:
    """Stream one upload to disk below `directory`, or raise a 4xx explaining why not."""
    target = safe_relative_path(relative_path or upload.filename or "", fallback_name)
    name = target.name

    if not name.lower().endswith(allowed_suffixes):
        detail = f'"{name}" is not {kind}.'
        raise HTTPException(status_code=400, detail=f"{detail} {hint}".strip())

    destination = directory / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with destination.open("wb") as handle:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            written += len(chunk)
            if written > max_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"{name} is larger than {max_bytes // (1024 * 1024)} MB.",
                )
            handle.write(chunk)

    if written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{name} is empty.")

    return destination
