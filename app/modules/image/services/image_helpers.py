"""Shared helpers for the image tool services."""


from PIL import Image, ImageFont

from app.infrastructure.compression.pillow_adapter import _parse_color
from app.shared.utils.image_util import load_image

SUPPORTED_CONVERSION_FORMATS = {"jpg", "png", "webp", "avif"}
SUPPORTED_RESIZE_FORMATS = {"jpg", "png", "webp"}
SUPPORTED_OUTPUT_FORMATS = {"auto", "jpg", "jpeg", "png", "webp"}
SUPPORTED_CROP_FORMATS = {"auto", "jpg", "jpeg", "png", "webp"}

POSITION_ALIASES = {
    "top-left": ("left", "top"),
    "top-right": ("right", "top"),
    "bottom-left": ("left", "bottom"),
    "bottom-right": ("right", "bottom"),
    "center": ("center", "center"),
}


def open_image(file_data: bytes) -> Image.Image:
    """Decode an upload with EXIF orientation applied and a safe mode."""
    return load_image(file_data)


def is_animated(image: Image.Image) -> bool:
    n_frames = getattr(image, "n_frames", 1)
    duration = image.info.get("duration")
    return (
        n_frames > 1
        or (
            duration is not None
            and isinstance(duration, list)
            and len(duration) > 1
        )
    )


def has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA"):
        return True
    return bool(image.mode == "P" and "transparency" in image.info)


def prepare_for_output(
    image: Image.Image,
    output_format: str,
    background_color: str | None,
) -> tuple[Image.Image, bool]:
    """Return (image, was_flattened) adjusting mode for output_format."""
    flattened = False

    if image.mode == "CMYK":
        image = image.convert("RGB")

    if output_format in ("jpg", "jpeg"):
        if has_transparency(image):
            bg_color = _parse_color(background_color)
            background = Image.new("RGB", image.size, bg_color)
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.getchannel("A"))
            image = background
            flattened = True
        elif image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

    return image, flattened


def default_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()
