"""Shared image preparation and encoding helpers for compression."""


from PIL import Image

from app.infrastructure.compression.pillow_adapter import (
    pillow_adapter,
)
from app.modules.compression.image_compression.image_compression_settings import (
    PRESETS,
)
from app.shared.utils.image_util import load_image


def prepare_image(
    file_data: bytes,
    max_dimension: int | None = None,
    strip_metadata: bool = True,
) -> Image.Image:
    """Open an image, optionally downscaling to ``max_dimension``."""
    image = load_image(file_data)

    if max_dimension:
        image.thumbnail(
            (max_dimension, max_dimension),
            Image.Resampling.LANCZOS,
        )

    return image


def encode(
    image: Image.Image,
    output_format: str,
    quality: int,
    strip_metadata: bool = True,
) -> tuple[bytes, str]:
    """Encode an image in the requested format, returning data and mime."""
    output_format = output_format.lower()

    if output_format == "webp":
        return (
            pillow_adapter.encode_webp(
                image,
                quality=quality,
                strip_metadata=strip_metadata,
            ),
            "image/webp",
        )

    if output_format == "jpeg":
        return (
            pillow_adapter.encode_jpeg(
                image,
                quality=quality,
                strip_metadata=strip_metadata,
            ),
            "image/jpeg",
        )

    if output_format == "png":
        return (
            pillow_adapter.encode_png(
                image,
                strip_metadata=strip_metadata,
            ),
            "image/png",
        )

    raise ValueError(f"Unsupported output format: {output_format}")


def get_preset(preset: str):
    """Look up a preset, raising ValueError for unknown names."""
    settings = PRESETS.get(preset)
    if not settings:
        raise ValueError(f"Unsupported compression preset: {preset}")
    return settings
