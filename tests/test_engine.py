"""Whole run behaviour, exercised through the real download path."""

from __future__ import annotations

import pandas as pd
import pytest

from app.processing import ProcessingConfig, ProcessingError, run
from app.processing.engine import PROCESS_LOG_NAME


def collect(source_path, output_dir, config=None, hmy_path=None):
    events = []
    summary = run(
        config=config or ProcessingConfig(),
        source_path=source_path,
        hmy_path=hmy_path,
        output_dir=output_dir,
        on_event=events.append,
    )
    return summary, events


def outputs(output_dir):
    return sorted(
        str(path.relative_to(output_dir)).replace("\\", "/")
        for path in output_dir.rglob("*")
        if path.is_file()
    )


class TestSuccessfulRun:
    def test_files_land_in_property_and_doc_type_folders(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        output = tmp_path / "out"
        summary, _ = collect(source, output)

        assert summary.succeeded == 1
        assert "p001__PHOTO_GALLERY/p001_wide_40_PG.jpg" in outputs(output)

    def test_a_target_property_redirects_the_folder_and_the_name(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,Chestnut Hill,"]
        )
        output = tmp_path / "out"
        collect(source, output)

        assert "Chestnut_Hill__PHOTO_GALLERY/Chestnut_Hill_wide_40_PG.jpg" in outputs(output)

    def test_a_target_image_name_replaces_all_automatic_naming(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,1 Bed/1 Bath.png"]
        )
        output = tmp_path / "out"
        collect(source, output)

        assert "p001__PHOTO_GALLERY/1 Bed_1 Bath.png" in outputs(output)

    def test_the_extension_in_a_target_name_decides_the_format(self, write_source, tmp_path, image_server):
        from PIL import Image

        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,forced.png"]
        )
        output = tmp_path / "out"
        collect(source, output)

        assert Image.open(output / "p001__PHOTO_GALLERY" / "forced.png").format == "PNG"

    def test_rename_only_mode_leaves_dimensions_alone(self, write_source, tmp_path, image_server):
        from PIL import Image

        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        output = tmp_path / "out"
        collect(source, output, ProcessingConfig(operationmode=1))

        assert Image.open(output / "p001__PHOTO_GALLERY" / "p001_wide_40_PG.jpg").size == (3000, 2000)

    def test_manual_sizing_overrides_the_itype_rule(self, write_source, tmp_path, image_server):
        from PIL import Image

        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        output = tmp_path / "out"
        collect(source, output, ProcessingConfig(manualsizing=1, targetwidth=670, targetheight=670))

        assert Image.open(output / "p001__PHOTO_GALLERY" / "p001_wide_40_PG.jpg").size == (670, 670)


class TestRowHandling:
    def test_inactive_rows_are_skipped(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Inactive,{image_server}/wide.jpg,,"]
        )
        summary, events = collect(source, tmp_path / "out")

        assert summary.skipped == 1
        assert summary.succeeded == 0
        assert any(event.level == "skip" for event in events)

    def test_a_failed_row_does_not_stop_the_ones_after_it(self, write_source, tmp_path, image_server):
        source = write_source(
            [
                f"p001,Ridgecrest,gone.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/gone.jpg,,",
                f"p001,Ridgecrest,wide.jpg,40,2,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,",
            ]
        )
        output = tmp_path / "out"
        summary, _ = collect(source, output)

        assert (summary.succeeded, summary.failed) == (1, 1)
        assert summary.failed_log_path is not None

    def test_row_numbers_match_the_spreadsheet_line(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        _, events = collect(source, tmp_path / "out")

        rows = [event.row for event in events if event.row is not None]
        assert rows == [2]

    def test_an_empty_url_is_reported_rather_than_crashing(self, write_source, tmp_path):
        source = write_source(["p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,,,"])
        summary, events = collect(source, tmp_path / "out")

        assert summary.failed == 1
        assert any("Full Path" in event.message for event in events)


class TestPropertyMapping:
    def test_a_p_code_url_is_retried_against_the_mapped_id(self, write_source, tmp_path, image_server):
        """The mapped id rewrites /2/<old>/ to /3/<id>/, which is where the file is."""
        mapping = tmp_path / "PropertyHMY.csv"
        mapping.write_text("Property Code,Property Id\np001,50653\n", encoding="utf-8")

        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/dmslivecafe/2/1/wide.jpg,,"]
        )
        output = tmp_path / "out"
        summary, events = collect(source, output, hmy_path=mapping)

        # The served directory has no dmslivecafe path, so both attempts 404.
        assert summary.failed == 1
        assert any("Loaded 1 property id mappings" in event.message for event in events)

    def test_a_missing_mapping_file_only_warns(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        summary, events = collect(source, tmp_path / "out", hmy_path=tmp_path / "nope.csv")

        assert summary.succeeded == 1
        assert any(event.level == "warning" for event in events)


class TestLogs:
    def test_the_process_log_records_paths_relative_to_the_output(self, write_source, tmp_path, image_server):
        source = write_source(
            [f"p001,Ridgecrest,wide.jpg,40,1,PHOTO GALLERY,,Active,{image_server}/wide.jpg,,"]
        )
        output = tmp_path / "out"
        collect(source, output)

        log = pd.read_csv(output / PROCESS_LOG_NAME)
        assert log.loc[0, "status"] == "success"
        assert not str(log.loc[0, "New"]).startswith(str(output))


class TestFailures:
    def test_a_missing_source_file_is_reported_immediately(self, tmp_path):
        with pytest.raises(ProcessingError, match="Source file not found"):
            run(ProcessingConfig(), tmp_path / "nope.csv", output_dir=tmp_path / "out")

    def test_a_missing_source_file_is_reported_without_a_mapping_file(self, tmp_path):
        """Regression: this check used to sit inside the mapping file branch."""
        with pytest.raises(ProcessingError):
            run(ProcessingConfig(), tmp_path / "nope.csv", hmy_path=None, output_dir=tmp_path / "out")

    def test_an_empty_source_file_is_reported(self, tmp_path):
        source = tmp_path / "empty.csv"
        source.write_text("", encoding="utf-8")
        with pytest.raises(ProcessingError, match="empty"):
            run(ProcessingConfig(), source, output_dir=tmp_path / "out")
