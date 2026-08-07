"""The flatten settings form: validation, and staying in step with the library."""

from __future__ import annotations

import pytest

from app.tools.flatten.options import FlattenSettings


class TestValidation:
    def test_the_defaults_are_usable_on_their_own(self):
        settings = FlattenSettings.from_mapping({})
        assert settings == FlattenSettings()

    def test_an_unknown_engine_is_rejected_by_name(self):
        with pytest.raises(ValueError, match="Engine must be one of"):
            FlattenSettings.from_mapping({"engine": "magic"})

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("verify_dpi", "12"),
            ("verify_dpi", "5000"),
            ("raster_dpi", "10"),
            ("raster_dpi", "5000"),
            ("tolerance", "-1"),
            ("tolerance", "0.9"),
        ],
    )
    def test_values_outside_the_sensible_range_are_rejected(self, field, value):
        with pytest.raises(ValueError, match="must be between"):
            FlattenSettings.from_mapping({field: value})

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", True])
    def test_the_ways_a_browser_says_yes(self, value):
        assert FlattenSettings.from_mapping({"allow_raster": value}).allow_raster is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", False])
    def test_the_ways_a_browser_says_no(self, value):
        assert FlattenSettings.from_mapping({"verify": value}).verify is False

    def test_nonsense_in_a_toggle_is_reported(self):
        with pytest.raises(ValueError, match="must be yes or no"):
            FlattenSettings.from_mapping({"verify": "maybe"})

    def test_nonsense_in_a_number_is_reported(self):
        with pytest.raises(ValueError, match="must be a whole number"):
            FlattenSettings.from_mapping({"verify_dpi": "lots"})

    def test_a_blank_number_falls_back_to_the_default(self):
        assert FlattenSettings.from_mapping({"verify_dpi": ""}).verify_dpi == 72


class TestLibraryAgreement:
    """The form duplicates the library's defaults. Catch it if they ever diverge."""

    def test_the_defaults_match_the_library(self):
        flatten_pdf = pytest.importorskip("flatten_pdf")

        ours = FlattenSettings()
        theirs = flatten_pdf.FlattenOptions()

        for field, value in ours.to_dict().items():
            assert value == getattr(theirs, field), f"default for {field!r} has drifted"

    def test_the_engine_list_matches_the_library(self):
        flatten_pdf = pytest.importorskip("flatten_pdf")

        from app.tools.flatten.options import ENGINES

        assert set(ENGINES) == set(flatten_pdf.ENGINES)

    def test_every_setting_is_accepted_by_the_library(self):
        pytest.importorskip("flatten_pdf")

        options = FlattenSettings().to_flatten_options()
        assert options.engine == "auto"

    def test_every_field_has_wording_for_the_form(self):
        from app.tools.flatten.options import FIELD_DESCRIPTIONS

        assert set(FIELD_DESCRIPTIONS) == set(FlattenSettings().to_dict())
