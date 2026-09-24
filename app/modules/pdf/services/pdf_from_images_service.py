"""Images to PDF conversion service."""

import time
from io import BytesIO

from PIL import Image

from app.core.logging import get_tool_logger
from app.shared.utils.image_util import load_image


def _as_pdf_page(data: bytes) -> Image.Image:
    """Decode an image as an upright RGB/L page.

    Transparent areas are flattened onto white (a plain ``convert("RGB")``
    turns them black) and EXIF orientation is applied.
    """
    image = load_image(data)
    if image.mode == "P":
        image = image.convert("RGBA")
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    if image.mode not in ("RGB", "L"):
        return image.convert("RGB")
    return image


class PdfFromImagesService:

    def from_images(
        self,
        images: list[tuple[str, bytes]],
    ) -> tuple[bytes, int]:
        tool_logger = get_tool_logger("image-to-pdf")
        started = time.monotonic()
        if not images:
            raise ValueError("No images were provided.")
        pages = [_as_pdf_page(data) for _, data in images]
        output_buffer = BytesIO()
        pages[0].save(
            output_buffer,
            format="PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=150,
        )
        data = output_buffer.getvalue()
        tool_logger.info(
            "created PDF from %d images (%d bytes) in %.2fs",
            len(pages),
            len(data),
            time.monotonic() - started,
        )
        return data, len(pages)


pdf_from_images_service = PdfFromImagesService()
