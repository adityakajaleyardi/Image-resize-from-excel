"""Generated filenames are a contract with downstream systems."""

from __future__ import annotations

import pytest

from app.processing.naming import (
    build_auto_filename,
    clean_key,
    clean_string,
    describes_doc_type,
    get_doc_type_abbreviation,
    get_filename_from_url,
    sanitise_target_image_name,
)


def build(**overrides) -> str:
    defaults = {
        "source_url": "https://www.rentcafe.com/dmslivecafe/3/50653/bedroom%20view.jpg",
        "original_property": "p0054389",
        "target_property": "Ridgecrest Village",
        "doc_type": "PHOTO GALLERY",
        "itype": "40",
        "extension": ".jpg",
        "add_optimized_suffix": False,
    }
    return build_auto_filename(**{**defaults, **overrides})


class TestCleanString:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Ridgecrest Village", "Ridgecrest_Village"),
            ("1 Bed/1 Bath -- Dining", "1_Bed_1_Bath_Dining"),
            ("__leading and trailing__", "leading_and_trailing"),
            ("", ""),
        ],
    )
    def test_collapses_runs_of_separators(self, raw, expected):
        assert clean_string(raw) == expected


class TestCleanKey:
    @pytest.mark.parametrize(
        "raw", ["Max File Size MB", "maxfilesizemb", "Max_File_Size_MB", "max-file-size-mb"]
    )
    def test_config_labels_all_resolve_to_one_key(self, raw):
        assert clean_key(raw) == "maxfilesizemb"


class TestDocTypes:
    def test_known_type_maps_to_its_abbreviation(self):
        assert get_doc_type_abbreviation("photo gallery") == "PG"

    def test_unknown_type_falls_back(self):
        assert get_doc_type_abbreviation("Something New") == "XX"

    @pytest.mark.parametrize("filename", ["property_floorplan_2", "FloorPlan copy", "unit fp 3"])
    def test_detects_a_type_already_named_in_the_file(self, filename):
        assert describes_doc_type(filename, "FP")

    def test_does_not_detect_an_unrelated_name(self):
        assert not describes_doc_type("kitchen_wide", "FP")


class TestFilenameFromUrl:
    def test_decodes_percent_escapes(self):
        assert get_filename_from_url("http://x/a/bed%20room.jpg") == "bed room.jpg"


class TestBuildAutoFilename:
    def test_combines_property_description_itype_and_doc_type(self):
        assert build() == "Ridgecrest_Village_bedroom_view_40_PG.jpg"

    def test_strips_the_property_code_the_export_prefixes(self):
        name = build(source_url="https://x/p0054389_kitchen.jpg")
        assert name == "Ridgecrest_Village_kitchen_40_PG.jpg"

    def test_does_not_repeat_a_doc_type_the_filename_already_states(self):
        name = build(source_url="https://x/floorplan_a.jpg", doc_type="FLOOR PLAN")
        assert name == "Ridgecrest_Village_floorplan_a_40.jpg"

    def test_does_not_repeat_an_itype_already_in_the_filename(self):
        name = build(source_url="https://x/kitchen_40.jpg")
        assert name == "Ridgecrest_Village_kitchen_40_PG.jpg"

    def test_omits_the_itype_when_it_is_zero(self):
        assert build(itype="0") == "Ridgecrest_Village_bedroom_view_PG.jpg"

    def test_omits_the_suffix_for_an_unmapped_doc_type(self):
        assert build(doc_type="Mystery") == "Ridgecrest_Village_bedroom_view_40.jpg"

    def test_appends_optimized_when_asked(self):
        name = build(add_optimized_suffix=True)
        assert name == "Ridgecrest_Village_bedroom_view_40_PG_Optimized.jpg"

    def test_uses_the_given_extension(self):
        assert build(extension=".png").endswith(".png")


class TestSanitiseTargetImageName:
    def test_replaces_characters_windows_rejects(self):
        assert sanitise_target_image_name("1 Bed/1 Bath.jpg", ".jpg") == "1 Bed_1 Bath.jpg"

    def test_keeps_an_extension_the_user_supplied(self):
        assert sanitise_target_image_name("logo.png", ".jpg") == "logo.png"

    def test_adds_the_detected_extension_when_there_is_none(self):
        assert sanitise_target_image_name("logo", ".jpg") == "logo.jpg"

    def test_collapses_repeated_underscores_from_stripped_characters(self):
        assert sanitise_target_image_name("a<>?b.jpg", ".jpg") == "a_b.jpg"
