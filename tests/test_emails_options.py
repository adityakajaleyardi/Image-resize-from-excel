"""The email converter's form settings."""

from __future__ import annotations

import pytest

from app.tools.emails.options import (
    LAYOUT_AUTO,
    LAYOUT_COLUMNS,
    LAYOUT_CSV_EXPORT,
    LAYOUT_LEGACY_XLSX,
    LAYOUTS,
    EmailSettings,
)


class TestDefaults:
    def test_an_empty_form_detects_the_layout_and_renders_images(self):
        settings = EmailSettings.from_mapping({})

        assert settings.column_layout == LAYOUT_AUTO
        assert settings.render_images is True

    def test_blank_fields_fall_back_to_the_defaults(self):
        settings = EmailSettings.from_mapping({"column_layout": "", "render_images": ""})

        assert settings == EmailSettings()


class TestValidation:
    @pytest.mark.parametrize("layout", sorted(LAYOUTS))
    def test_every_offered_layout_is_accepted(self, layout):
        assert EmailSettings.from_mapping({"column_layout": layout}).column_layout == layout

    def test_an_unknown_layout_is_refused(self):
        with pytest.raises(ValueError, match="Column layout must be one of"):
            EmailSettings.from_mapping({"column_layout": "guesswork"})

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("1", True), ("0", False), ("true", True), ("no", False), ("on", True)],
    )
    def test_the_screenshot_switch_reads_the_usual_spellings(self, value, expected):
        assert EmailSettings.from_mapping({"render_images": value}).render_images is expected

    def test_a_nonsense_screenshot_value_is_refused(self):
        with pytest.raises(ValueError, match="must be true or false"):
            EmailSettings.from_mapping({"render_images": "maybe"})

    def test_settings_survive_a_round_trip_through_a_dict(self):
        settings = EmailSettings(column_layout=LAYOUT_LEGACY_XLSX, render_images=False)

        assert EmailSettings.from_mapping(settings.to_dict()) == settings


class TestLibraryAgreement:
    """The column names are duplicated so the form works without the library.

    If the library ever renames a column, this fails rather than the app quietly
    offering a layout that no longer exists.
    """

    @pytest.fixture(autouse=True)
    def library(self):
        pytest.importorskip("greystar_email_converter")

    def test_the_csv_layout_matches_the_library(self):
        from greystar_email_converter import ColumnMapping

        mapping = ColumnMapping.csv_export()
        assert LAYOUT_COLUMNS[LAYOUT_CSV_EXPORT] == (mapping.body, mapping.name)

    def test_the_legacy_layout_matches_the_library(self):
        from greystar_email_converter import ColumnMapping

        mapping = ColumnMapping.legacy_xlsx()
        assert LAYOUT_COLUMNS[LAYOUT_LEGACY_XLSX] == (mapping.body, mapping.name)

    def test_detecting_asks_the_library_for_nothing(self):
        assert EmailSettings(column_layout=LAYOUT_AUTO).to_column_mapping() is None

    @pytest.mark.parametrize("layout", [LAYOUT_CSV_EXPORT, LAYOUT_LEGACY_XLSX])
    def test_a_chosen_layout_becomes_the_librarys_own_object(self, layout):
        mapping = EmailSettings(column_layout=layout).to_column_mapping()

        assert (mapping.body, mapping.name) == LAYOUT_COLUMNS[layout]
