"""Shared fixtures.

`image_server` serves real files over HTTP so the engine can be tested through
its normal download path rather than with a stubbed session.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from PIL import Image

SOURCE_HEADER = (
    "Property/Company Code,Property Name,File Name,iType,Order,Doc. Type,"
    "Floorplan Code,Active/Inactive,Full Path,Target Property,Target Image Name"
)


@pytest.fixture(autouse=True)
def allow_the_test_server(monkeypatch):
    """Permit downloads from the local test server.

    Only rentcafe.com is allowed by default, which is the point of the
    restriction, so tests have to opt the fixture server in explicitly.
    """
    from app.processing import constants

    monkeypatch.setattr(
        constants,
        "ALLOWED_HOST_SUFFIXES",
        (*constants.ALLOWED_HOST_SUFFIXES, "127.0.0.1"),
    )


@pytest.fixture(scope="session")
def image_server(tmp_path_factory) -> str:
    """Serve a landscape, a portrait and a small image, and return the base URL."""
    directory = tmp_path_factory.mktemp("served")
    Image.new("RGB", (3000, 2000), (120, 160, 200)).save(directory / "wide.jpg")
    Image.new("RGB", (800, 1600), (200, 120, 120)).save(directory / "tall.jpg")
    Image.new("RGB", (120, 90), (40, 40, 40)).save(directory / "small.jpg")
    Image.new("RGBA", (600, 400), (10, 90, 10, 255)).save(directory / "logo.png")

    handler = functools.partial(_QuietHandler, directory=str(directory))
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    yield f"http://127.0.0.1:{server.server_address[1]}"

    server.shutdown()
    server.server_close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - silence request logging
        pass


@pytest.fixture
def write_source(tmp_path: Path):
    """Write a source CSV from a header and rows of raw CSV text."""

    def _write(rows: list[str], name: str = "Source.csv") -> Path:
        path = tmp_path / name
        path.write_text("\n".join([SOURCE_HEADER, *rows]) + "\n", encoding="utf-8")
        return path

    return _write
