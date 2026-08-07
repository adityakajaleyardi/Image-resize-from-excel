"""Progress events and the error type tools raise.

Shared by every tool and by the job layer. This module must stay free of web and
third party dependencies so the command line entry points keep working on their
own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

LEVEL_INFO = "info"
LEVEL_OK = "ok"
LEVEL_SKIP = "skip"
LEVEL_WARNING = "warning"
LEVEL_FAIL = "fail"


class ToolError(Exception):
    """A run could not start or finish, for a reason worth showing the user.

    Anything else that escapes a runner is treated as a crash and reported as an
    unexpected error.
    """


@dataclass(frozen=True)
class Event:
    """One line of progress from a run."""

    level: str
    message: str
    row: int | None = None
    processed: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "row": self.row,
            "processed": self.processed,
            "total": self.total,
        }


EventCallback = Callable[[Event], None]
