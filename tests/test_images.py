"""Output dimensions are a contract, like filenames."""

from __future__ import annotations

import pytest
from PIL import Image

from app.processing.constants import PROPERTY_TYPE_LEGACY, PROPERTY_TYPE_MVC, get_target_box
from app.processing.images import compress_and_save, get_scaled_dimensions, resize_to_box


def _noisy_image(size: int) -> Image.Image:
    """Random noise, which JPEG cannot compress away."""
    import random

    rng = random.Random(0)
    image = Image.new("RGB", (size, size))
    image.putdata([(rng.randrange(256),) * 3 for _ in range(size * size)])
    return image


class TestTargetBox:
    @pytest.mark.parametrize(
        ("itype", "property_type", "expected"),
        [
            (1, PROPERTY_TYPE_MVC, (2560, 1707)),
            (1, PROPERTY_TYPE_LEGACY, (1024, 768)),
            (120, PROPERTY_TYPE_MVC, (2560, 1707)),
            (120, PROPERTY_TYPE_LEGACY, (670, 480)),
            (5, PROPERTY_TYPE_MVC, (500, 350)),
            (5, PROPERTY_TYPE_LEGACY, (500, 350)),
            (40, PROPERTY_TYPE_LEGACY, (99999, 1000)),
        ],
    )
    def test_known_types(self, itype, property_type, expected):
        assert get_target_box(itype, property_type) == expected

    @pytest.mark.parametrize("itype", ["40", "40.0", 40.0])
    def test_accepts_the_shapes_a_csv_cell_arrives_in(self, itype):
        assert get_target_box(itype, PROPERTY_TYPE_MVC) == (99999, 1000)

    @pytest.mark.parametrize("itype", ["", "abc", None, 999])
    def test_unknown_types_have_no_rule(self, itype):
        assert get_target_box(itype, PROPERTY_TYPE_MVC) is None

    def test_legacy_only_applies_to_types_it_defines(self):
        assert get_target_box(4, PROPERTY_TYPE_LEGACY) is None
        assert get_target_box(4, PROPERTY_TYPE_MVC) == (2560, 1707)


class TestScaledDimensions:
    def test_fits_inside_the_box_keeping_the_aspect_ratio(self):
        assert get_scaled_dimensions(3000, 2000, 1500, 1500) == (1500, 1000)

    def test_never_enlarges_by_default(self):
        assert get_scaled_dimensions(100, 80, 2560, 1707) == (100, 80)

    def test_enlarges_when_downscaling_is_not_enforced(self):
        assert get_scaled_dimensions(100, 80, 200, 200, downscale_only=False) == (200, 160)


class TestResizeToBox:
    def test_landscape_is_scaled_down_to_fit(self):
        image, action = resize_to_box(Image.new("RGB", (3000, 2000)), (2560, 1707), manual=False)
        assert image.size == (2560, 1706)
        assert "Resized" in action

    def test_portrait_is_cropped_before_scaling(self):
        image, action = resize_to_box(Image.new("RGB", (800, 1600)), (99999, 1000), manual=False)
        # 15 percent comes off each end first, leaving 800x1120.
        assert image.size == (714, 1000)
        assert "Vertical crop" in action

    def test_small_image_is_left_alone(self):
        image, action = resize_to_box(Image.new("RGB", (120, 90)), (2560, 1707), manual=False)
        assert image.size == (120, 90)
        assert action == "Kept (smaller than target)"

    def test_manual_sizing_stretches_to_the_exact_box(self):
        image, action = resize_to_box(Image.new("RGB", (120, 90)), (670, 670), manual=True)
        assert image.size == (670, 670)
        assert action == "Resized to 670x670"

    def test_manual_sizing_does_not_crop_portraits(self):
        image, _ = resize_to_box(Image.new("RGB", (800, 1600)), (670, 670), manual=True)
        assert image.size == (670, 670)


class TestCompressAndSave:
    def test_jpeg_quality_drops_until_it_meets_the_limit(self, tmp_path):
        image = _noisy_image(1200)
        generous = compress_and_save(image, tmp_path / "big.jpg", max_mb=10)
        constrained = compress_and_save(image, tmp_path / "small.jpg", max_mb=0.3)

        assert constrained <= 0.3 < generous

    def test_an_incompressible_image_is_still_written(self, tmp_path):
        """Quality stops at a usable floor, so the limit is a target, not a guarantee."""
        path = tmp_path / "out.jpg"
        size_mb = compress_and_save(_noisy_image(2000), path, max_mb=0.01)

        assert path.exists()
        assert size_mb > 0.01

    def test_png_keeps_transparency(self, tmp_path):
        path = tmp_path / "out.png"
        compress_and_save(Image.new("RGBA", (50, 50), (0, 0, 0, 0)), path, 1.0, format_type="PNG")
        assert Image.open(path).mode == "RGBA"
