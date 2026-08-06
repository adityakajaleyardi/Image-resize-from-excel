"""Config parsing has to survive whatever a spreadsheet produces."""

from __future__ import annotations

import pytest

from app.processing.config import ProcessingConfig


class TestDefaults:
    def test_resize_mode_with_automatic_sizing(self):
        config = ProcessingConfig()
        assert config.is_resize_mode
        assert not config.uses_manual_sizing
        assert not config.adds_optimized_suffix


class TestFromMapping:
    def test_matches_keys_regardless_of_spacing_and_case(self):
        config = ProcessingConfig.from_mapping(
            {"Max File Size MB": "2.5", "Property Type": "legacy", "Target Width": "670"}
        )
        assert config.maxfilesizemb == 2.5
        assert config.propertytype == "LEGACY"
        assert config.targetwidth == 670

    def test_reads_numbers_that_arrive_as_floats(self):
        assert ProcessingConfig.from_mapping({"operationmode": "1.0"}).operationmode == 1

    @pytest.mark.parametrize("value", ["yes", "true", "on", "1"])
    def test_accepts_the_ways_a_toggle_is_written(self, value):
        assert ProcessingConfig.from_mapping({"manualsizing": value}).uses_manual_sizing

    @pytest.mark.parametrize("value", ["no", "false", "off", "0"])
    def test_accepts_the_ways_a_toggle_is_turned_off(self, value):
        assert not ProcessingConfig.from_mapping({"manualsizing": value}).uses_manual_sizing

    def test_ignores_unknown_settings(self):
        assert ProcessingConfig.from_mapping({"colour scheme": "blue"}) == ProcessingConfig()

    def test_falls_back_to_the_default_for_an_unreadable_value(self):
        config = ProcessingConfig.from_mapping({"targetwidth": "wide please"})
        assert config.targetwidth == ProcessingConfig().targetwidth

    def test_ignores_blank_cells(self):
        config = ProcessingConfig.from_mapping({"targetheight": "  ", "propertytype": None})
        assert config == ProcessingConfig()


class TestValidation:
    @pytest.mark.parametrize(
        "invalid",
        [
            {"operationmode": 3},
            {"propertytype": "OTHER"},
            {"targetwidth": 0},
            {"targetheight": -5},
            {"maxfilesizemb": 0},
        ],
    )
    def test_rejects_values_that_cannot_work(self, invalid):
        with pytest.raises(ValueError):
            ProcessingConfig(**invalid)


class TestFromFile:
    def test_reads_the_three_column_config_the_desktop_version_used(self, tmp_path):
        path = tmp_path / "Config.csv"
        path.write_text(
            "Setting Name,Value,Description (Optional)\n"
            "Source File,img_Report.csv,Name of the data file\n"
            "Target Width,670,Width in pixels\n"
            "Operation Mode,1,1 = Rename Only\n"
            "Property Type,Legacy,MVC or Legacy\n",
            encoding="utf-8",
        )
        config = ProcessingConfig.from_file(path)

        assert config.sourcefile == "img_Report.csv"
        assert config.targetwidth == 670
        assert config.operationmode == 1
        assert config.propertytype == "LEGACY"

    def test_discover_prefers_a_config_in_the_folder(self, tmp_path):
        (tmp_path / "Config.csv").write_text("Max File Size MB,3\n", encoding="utf-8")
        config, path = ProcessingConfig.discover(tmp_path)
        assert config.maxfilesizemb == 3
        assert path is not None

    def test_discover_falls_back_to_defaults(self, tmp_path):
        config, path = ProcessingConfig.discover(tmp_path)
        assert path is None
        assert config == ProcessingConfig()
