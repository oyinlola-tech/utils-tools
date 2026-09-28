"""Image resizing logic for the image-resizer tool."""

import time

from PIL import Image

from app.core.logging import get_tool_logger
from app.infrastructure.compression.pillow_adapter import pillow_adapter
from app.modules.image.services.image_helpers import (
    SUPPORTED_RESIZE_FORMATS,
    has_transparency,
    is_animated,
    open_image,
    prepare_for_output,
)
from app.modules.image.services.resize_math import (
    compute_new_size,
    validate_dimensions,
)


def _cover_box(
    source: tuple[int, int],
    target: tuple[int, int],
) -> tuple[float, float, float, float]:
    """The largest centred region of ``source`` with the shape of ``target``."""
    scale = max(target[0] / source[0], target[1] / source[1])
    width = min(source[0], target[0] / scale)
    height = min(source[1], target[1] / scale)
    left = (source[0] - width) / 2
    top = (source[1] - height) / 2
    return (left, top, left + width, top + height)


class ImageResizerService:
    """Resize images with aspect, exact, percent or max modes."""

    def resize(
        self,
        file_data: bytes,
        resize_mode: str = "aspect",
        width: int | None = None,
        height: int | None = None,
        percent: float | None = None,
        max_dimension: int | None = None,
        maintain_aspect_ratio: bool = True,
        allow_upscale: bool = False,
        output_format: str = "auto",
        quality: int | None = None,
        strip_metadata: bool = True,
        background_color: str | None = None,
        cover: bool = False,
    ) -> dict:
        """Resize an image with full control over dimensions and output.

        With ``cover`` an exact size is filled by cropping the image
        around its centre instead of stretching it.
        """
        tool_logger = get_tool_logger("image-resizer")
        started = time.monotonic()
        image = open_image(file_data)

        if is_animated(image):
            raise ValueError("Animated images are not supported for resizing.")

        input_format = (image.format or "unknown").upper()
        original_size = len(file_data)
        original_width = image.width
        original_height = image.height

        if image.mode == "CMYK":
            image = image.convert("RGB")

        validate_dimensions(width, height, percent, max_dimension, resize_mode)

        new_size = compute_new_size(
            image.width,
            image.height,
            resize_mode,
            width,
            height,
            percent,
            max_dimension,
            maintain_aspect_ratio,
            allow_upscale,
        )

        if new_size == (image.width, image.height):
            resized = image.copy()
        elif new_size[0] <= 0 or new_size[1] <= 0:
            raise ValueError("Calculated dimensions are not positive.")
        else:
            resized = image.resize(
                new_size,
                Image.Resampling.LANCZOS,
                box=_cover_box(image.size, new_size) if cover else None,
            )

        if output_format == "auto":
            fmt_map = {
                "JPEG": "jpg",
                "JPG": "jpg",
                "PNG": "png",
                "WEBP": "webp",
                "AVIF": "avif",
            }
            output_format = fmt_map.get(input_format, "png")

        output_format = output_format.lower()
        if output_format == "jpeg":
            # Accepted by the controller, so it has to work here too.
            output_format = "jpg"
        if output_format not in SUPPORTED_RESIZE_FORMATS:
            raise ValueError(
                f"Unsupported output format for resize: {output_format}. "
                "Use jpg, png or webp."
            )

        resized, flattened = prepare_for_output(
            resized,
            output_format,
            background_color,
        )

        if output_format in ("jpg", "jpeg") and quality is None:
            quality = 90
        elif output_format == "webp" and quality is None:
            quality = 95

        data, content_type = pillow_adapter.encode(
            resized,
            output_format,
            quality=quality or 92,
            strip_metadata=strip_metadata,
            background_color=background_color,
        )

        tool_logger.info(
            "resized %dx%d -> %dx%d (%d -> %d bytes, %s) in %.2fs",
            original_width,
            original_height,
            resized.width,
            resized.height,
            original_size,
            len(data),
            output_format,
            time.monotonic() - started,
        )
        return {
            "data": data,
            "content_type": content_type,
            "extension": "jpg" if output_format in ("jpg", "jpeg") else output_format,
            "width": resized.width,
            "height": resized.height,
            "input_format": input_format,
            "original_width": original_width,
            "original_height": original_height,
            "original_size": original_size,
            "output_size": len(data),
            "flattened": flattened,
            "has_alpha": has_transparency(resized) if not flattened else False,
        }


image_resizer_service = ImageResizerService()
