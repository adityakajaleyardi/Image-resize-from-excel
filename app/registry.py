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
    #: A few words for the home page tile, where the summary is too long to fit.
    tagline: str = ""
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
        label="Images from CSV",
        path="/images",
        help_path="/images/help",
        summary="Download, resize, rename and file property images listed in a CSV export.",
        tagline="From a CSV report",
    ),
    Tool(
        id="flatten",
        label="PDF Flatten",
        path="/flatten",
        help_path="/flatten/help",
        summary="Permanently bake form fields and annotations into a batch of PDFs.",
        tagline="Bake in form fields",
        requires=("flatten_pdf",),
        install_hint=("pip install git+https://github.com/adityakajaleyardi/Flatten.git"),
    ),
    Tool(
        id="folder",
        label="Images from Folder",
        path="/folder",
        help_path="/folder/help",
        summary="Resize, rename and file a folder of property images to the Yardi convention.",
        tagline="From a local folder",
        requires=("image_from_folder",),
        install_hint=("pip install -r requirements-folder.txt"),
    ),
    Tool(
        id="emails",
        label="Emails to HTML and Images",
        path="/emails",
        help_path="/emails/help",
        summary="Decode the compressed email bodies in an export into readable HTML and screenshots.",
        tagline="Decode an email export",
        requires=("greystar_email_converter",),
        install_hint=("pip install -r requirements-emails.txt"),
    ),
)


def get_tool(tool_id: str) -> Tool:
    for tool in TOOLS:
        if tool.id == tool_id:
            return tool
    raise KeyError(tool_id)
