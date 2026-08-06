"""Uploads are checked before a job starts, so the message has to be useful."""

from __future__ import annotations

import pytest

from app.processing.validation import (
    ValidationError,
    validate_property_hmy_csv,
    validate_source_csv,
)
from tests.conftest import SOURCE_HEADER


def write(tmp_path, text, name="file.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


class TestSourceValidation:
    def test_accepts_the_standard_export(self, tmp_path):
        path = write(tmp_path, SOURCE_HEADER + "\n")
        assert "Full Path" in validate_source_csv(path)

    def test_accepts_the_alternative_property_column(self, tmp_path):
        header = SOURCE_HEADER.replace("Property/Company Code", "Property Code")
        assert validate_source_csv(write(tmp_path, header + "\n"))

    def test_names_every_missing_column_at_once(self, tmp_path):
        path = write(tmp_path, "Property Code,File Name\n")
        with pytest.raises(ValidationError) as error:
            validate_source_csv(path)

        message = str(error.value)
        for expected in ("iType", "Doc. Type", "Active/Inactive", "Full Path"):
            assert expected in message

    def test_mentions_both_accepted_spellings(self, tmp_path):
        header = SOURCE_HEADER.replace("Property/Company Code", "Prop Code")
        with pytest.raises(ValidationError, match="Property/Company Code.*or.*Property Code"):
            validate_source_csv(write(tmp_path, header + "\n"))

    def test_rejects_an_empty_file(self, tmp_path):
        with pytest.raises(ValidationError):
            validate_source_csv(write(tmp_path, ""))

    def test_reads_a_file_saved_in_a_non_utf8_encoding(self, tmp_path):
        path = tmp_path / "latin.csv"
        path.write_bytes((SOURCE_HEADER + "\n").encode("latin-1"))
        assert validate_source_csv(path)


class TestPropertyMappingValidation:
    def test_accepts_the_misspelling_the_export_produces(self, tmp_path):
        path = write(tmp_path, " Propery Id, Propery Code, Reference Code\n20330,p0000488,101002\n")
        assert validate_property_hmy_csv(path) == ("Propery Code", "Propery Id")

    def test_accepts_the_correct_spelling(self, tmp_path):
        path = write(tmp_path, "Property Code,Property Id\np0054387,50651\n")
        assert validate_property_hmy_csv(path) == ("Property Code", "Property Id")

    def test_reports_a_missing_id_column(self, tmp_path):
        path = write(tmp_path, "Property Code,Name\np1,Somewhere\n")
        with pytest.raises(ValidationError, match="Propery Id"):
            validate_property_hmy_csv(path)
