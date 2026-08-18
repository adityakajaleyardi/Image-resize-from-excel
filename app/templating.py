"""The shared Jinja environment.

Values every page needs are registered as globals so individual routes only pass
what is specific to them.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from . import __version__
from .registry import TOOLS
from .settings import APP_NAME, JOB_RETENTION_HOURS

APP_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals.update(
    app_name=APP_NAME,
    tools=TOOLS,
    version=__version__,
    retention_hours=JOB_RETENTION_HOURS,
)
