import time

from PIL import Image, ImageFilter

from app.core.logging import get_tool_logger
from app.shared.utils.image_util import load_image


def _get_rembg_adapter():
    from app.infrastructure.image.rembg_adapter import rembg_adapter
    return rembg_adapter


class BackgroundService:
    def remove_background(
        self,
        file_data: bytes,
        original_filename: str,
    ) -> tuple[Image.Image, int, int]:
        tool_logger = get_tool_logger("background-remover")
        started = time.monotonic()
        image = load_image(file_data)
        width, height = image.size
        processed_image = (
            _get_rembg_adapter().remove_background(
                image,
            )
        )
        tool_logger.info(
            "removed background from %dx%d image (%s, %d bytes) in %.2fs",
            width,
            height,
            original_filename,
            len(file_data),
            time.monotonic() - started,
        )
        return (
            processed_image,
            width,
            height,
        )

    def replace_background(
        self,
        file_data: bytes,
        color: str | None = None,
        image_data: bytes | None = None,
        blur: int = 0,
    ) -> tuple[Image.Image, int, int]:
        """Remove the subject's background and place it on a solid
        color, an uploaded image, or a blurred copy of itself.
        """
        tool_logger = get_tool_logger("background-replacement")
        started = time.monotonic()
        source = load_image(file_data)
        width, height = source.size
        subject = _get_rembg_adapter().remove_background(source)

        if image_data is not None:
            try:
                background = load_image(image_data)
            except Exception as error:
                raise ValueError(
                    "The uploaded background image is not valid."
                ) from error
            background = background.convert("RGBA")
            if background.size != subject.size:
                background = background.resize(
                    subject.size,
                    Image.Resampling.LANCZOS,
                )
            if blur > 0:
                background = background.filter(
                    ImageFilter.GaussianBlur(blur)
                )
        elif color is not None:
            background = Image.new(
                "RGBA",
                subject.size,
                color,
            )
        else:
            blurred = source.convert("RGBA")
            background = blurred.filter(
                ImageFilter.GaussianBlur(blur or 20)
            )

        tool_logger.info(
            "replaced background of %dx%d image (mode=%s, blur=%d, %d bytes) in %.2fs",
            width,
            height,
            "image" if image_data is not None else ("color" if color is not None else "blur"),
            blur,
            len(file_data),
            time.monotonic() - started,
        )
        return (
            Image.alpha_composite(background, subject),
            width,
            height,
        )


background_service = BackgroundService()
