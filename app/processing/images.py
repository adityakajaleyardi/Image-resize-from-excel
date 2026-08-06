"""Image geometry and compression.

The dimensions produced here are contractual, like the filenames in `naming`.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from .constants import VERTICAL_CROP_RATIO

JPEG_START_QUALITY = 95
JPEG_MIN_QUALITY = 10
JPEG_QUALITY_STEP = 5


def process_vertical_image(img: Image.Image) -> Image.Image:
    """Trim equal slices off the top and bottom of a portrait image."""
    width, height = img.size
    crop = int(height * VERTICAL_CROP_RATIO)
    return img.crop((0, crop, width, height - crop))


def get_scaled_dimensions(
    img_w: int, img_h: int, target_w: int, target_h: int, downscale_only: bool = True
) -> tuple[int, int]:
    """Fit an image inside a target box while keeping its aspect ratio."""
    scale = min(target_w / img_w, target_h / img_h)
    if downscale_only and scale >= 1.0:
        return img_w, img_h
    return int(img_w * scale), int(img_h * scale)


def resize_to_box(img: Image.Image, box: tuple[int, int], manual: bool) -> tuple[Image.Image, str]:
    """Resize an image to a target box and describe what was done.

    With manual sizing the image is stretched to exactly the given dimensions.
    Otherwise it is scaled down to fit, and portrait images are cropped first so
    they are not reduced to a sliver inside a landscape box.
    """
    box_w, box_h = box
    original_w, original_h = img.size

    if manual:
        if (original_w, original_h) == (box_w, box_h):
            return img, f"Resized to {box_w}x{box_h}"
        return img.resize((box_w, box_h), Image.Resampling.LANCZOS), f"Resized to {box_w}x{box_h}"

    final_w, final_h = get_scaled_dimensions(original_w, original_h, box_w, box_h)
    if (final_w, final_h) == (original_w, original_h):
        return img, "Kept (smaller than target)"

    if original_h > original_w:
        img = process_vertical_image(img)
        final_w, final_h = get_scaled_dimensions(*img.size, box_w, box_h)
        img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
        return img, f"Vertical crop and resized to {final_w}x{final_h}"

    return img.resize((final_w, final_h), Image.Resampling.LANCZOS), f"Resized to {final_w}x{final_h}"


def compress_and_save(img: Image.Image, save_path: Path, max_mb: float, format_type: str = "JPEG") -> float:
    """Write an image to disk and return its final size in megabytes.

    PNGs are saved losslessly. JPEGs step down in quality until they fit the
    size limit, or until quality would drop below a usable level.
    """
    buffer = BytesIO()

    if format_type == "PNG":
        img.save(buffer, format="PNG", optimize=True)
    else:
        max_bytes = int(max_mb * 1024 * 1024)
        quality = JPEG_START_QUALITY
        while quality >= JPEG_MIN_QUALITY:
            buffer.seek(0)
            buffer.truncate(0)
            img.save(buffer, format="JPEG", quality=quality)
            if buffer.tell() <= max_bytes:
                break
            quality -= JPEG_QUALITY_STEP

    Path(save_path).write_bytes(buffer.getbuffer())
    return buffer.tell() / (1024 * 1024)
