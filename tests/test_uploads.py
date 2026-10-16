"""Filenames from the browser are hostile input. These are the cases that matter."""

from __future__ import annotations

import pytest

from app.uploads import safe_name, safe_relative_path


class TestSafeRelativePath:
    def test_a_folder_structure_is_kept(self):
        assert safe_relative_path("Invoices/2024/march.pdf", "x.pdf").as_posix() == (
            "Invoices/2024/march.pdf"
        )

    def test_backslashes_are_treated_as_separators(self):
        assert safe_relative_path("Invoices\\2024\\march.pdf", "x.pdf").as_posix() == (
            "Invoices/2024/march.pdf"
        )

    @pytest.mark.parametrize(
        "hostile",
        [
            "../../../etc/passwd",
            "..\\..\\Windows\\System32\\config",
            "folder/../../../secret.pdf",
        ],
    )
    def test_dot_dot_can_never_climb_out(self, hostile):
        result = safe_relative_path(hostile, "fallback.pdf")
        assert ".." not in result.parts
        assert not result.is_absolute()

    def test_a_drive_letter_is_dropped(self):
        assert safe_relative_path("C:\\Users\\bob\\report.pdf", "x.pdf").as_posix() == (
            "Users/bob/report.pdf"
        )

    def test_an_absolute_posix_path_becomes_relative(self):
        result = safe_relative_path("/etc/hosts.pdf", "x.pdf")
        assert not result.is_absolute()
        assert result.as_posix() == "etc/hosts.pdf"

    def test_an_empty_path_falls_back(self):
        assert safe_relative_path("", "fallback.pdf").as_posix() == "fallback.pdf"
        assert safe_relative_path("///", "fallback.pdf").as_posix() == "fallback.pdf"

    def test_characters_windows_refuses_are_replaced(self):
        assert safe_relative_path("we<ir>d|name?.pdf", "x.pdf").as_posix() == "we_ir_d_name_.pdf"

    def test_a_very_deep_path_is_trimmed(self):
        deep = "/".join(f"level{index}" for index in range(40)) + "/file.pdf"
        result = safe_relative_path(deep, "x.pdf")
        assert len(result.parts) <= 12
        assert result.name == "file.pdf"


class TestSafeName:
    def test_directories_are_stripped(self):
        assert safe_name("some/folder/report.pdf", "x.pdf") == "report.pdf"

    def test_an_empty_name_falls_back(self):
        assert safe_name("", "fallback.pdf") == "fallback.pdf"
        assert safe_name("...", "fallback.pdf") == "fallback.pdf"

    def test_a_long_name_keeps_its_extension(self):
        result = safe_name("a" * 400 + ".pdf", "x.pdf")
        assert len(result) <= 120
        assert result.endswith(".pdf")
