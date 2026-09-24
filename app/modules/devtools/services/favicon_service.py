"""Favicon generation for the favicon-generator tool."""

import time
from io import BytesIO

from PIL import Image

from app.core.logging import get_tool_logger
from app.modules.devtools.services.devtools_helpers import favicon_sizes
from app.shared.utils.image_util import load_image

_VALID_SIZES = (16, 32, 48, 64, 128, 180, 256)


class FaviconService:
    """Create a favicon set (ICO + PNGs) from a source image."""

    def generate_favicon(
        self,
        image_data: bytes,
        size: int = 64,
        add_padding: bool = False,
    ) -> dict:
        """Create a favicon set (ICO + PNGs) from a source image."""
        tool_logger = get_tool_logger("favicon-generator")
        started = time.monotonic()
        source = load_image(image_data)
        square = source.convert("RGBA")
        if square.width != square.height:
            side = min(square.size)
            square = square.crop(
                (
                    (square.width - side) // 2,
                    (square.height - side) // 2,
                    (square.width + side) // 2,
                    (square.height + side) // 2,
                )
            )
        if add_padding:
            pad = max(1, round(square.width * 0.1))
            canvas = Image.new(
                "RGBA",
                (square.width + pad * 2, square.height + pad * 2),
                (0, 0, 0, 0),
            )
            canvas.paste(square, (pad, pad))
            square = canvas
        if size not in _VALID_SIZES:
            size = 64
        sizes = [16, 32, 48]
        if size > 48:
            sizes.append(size)
        ico_buffer = BytesIO()
        frames = [favicon_sizes(square, item) for item in sizes]
        frames[0].save(
            ico_buffer,
            format="ICO",
            sizes=[(item, item) for item in sizes],
            append_images=frames[1:],
        )
        png_buffer = BytesIO()
        favicon_sizes(square, size).save(png_buffer, format="PNG")
        tool_logger.info(
            "generated favicon set %s (ico %d, png %d bytes) in %.2fs",
            sizes,
            ico_buffer.getbuffer().nbytes,
            png_buffer.getbuffer().nbytes,
            time.monotonic() - started,
        )
        return {
            "ico": ico_buffer.getvalue(),
            "png": png_buffer.getvalue(),
            "sizes": sizes,
        }


favicon_service = FaviconService()
