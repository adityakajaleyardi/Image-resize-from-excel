"""The tools this server offers.

Drives the navigation tabs and the availability check. A tool whose dependency is
not installed still appears, but says so instead of failing at import time and
taking the other tools down with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class Tool:
    id: str
    label: str
    path: str
    help_path: str
    summary: str
    #: Import names that must be installed for this tool to run.
    requires: tuple[str, ...] = ()
    #: How to install them, shown when they are missing.
    install_hint: str = ""

    @property
    def missing_requirement(self) -> str | None:
        for module in self.requires:
            try:
                if find_spec(module) is None:
                    return module
            except (ImportError, ValueError):
                return module
        return None

    @property
    def available(self) -> bool:
        return self.missing_requirement is None


TOOLS: tuple[Tool, ...] = (
    Tool(
        id="images",
        label="Images",
        path="/images",
        help_path="/images/help",
        summary="Download, resize, rename and file property images listed in a CSV export.",
    ),
    Tool(
        id="flatten",
        label="PDF Flatten",
        path="/flatten",
        help_path="/flatten/help",
        summary="Permanently bake form fields and annotations into a batch of PDFs.",
        requires=("flatten_pdf",),
        install_hint=("pip install git+https://github.com/adityakajaleyardi/Flatten.git"),
    ),
)


def get_tool(tool_id: str) -> Tool:
    for tool in TOOLS:
        if tool.id == tool_id:
            return tool
    raise KeyError(tool_id)
