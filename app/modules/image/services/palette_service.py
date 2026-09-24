"""Color palette extraction for the palette-extractor tool."""

import time

from app.core.logging import get_tool_logger
from app.shared.utils.image_util import load_image


class PaletteExtractorService:
    """Extract a dominant color palette from an image."""

    def extract_palette(
        self,
        image_data: bytes,
        num_colors: int = 6,
    ) -> list[dict]:
        tool_logger = get_tool_logger("palette-extractor")
        started = time.monotonic()
        if not 1 <= num_colors <= 32:
            raise ValueError("Number of colours must be between 1 and 32.")
        img = load_image(image_data)
        img = img.convert("RGB")
        img.thumbnail((150, 150))
        quantized = img.quantize(colors=num_colors)
        palette = quantized.getpalette()[: num_colors * 3]
        counts = quantized.getcolors()

        colors = []
        if counts:
            total_pixels = sum(count for count, _ in counts)
            for count, index in counts:
                r = palette[index * 3]
                g = palette[index * 3 + 1]
                b = palette[index * 3 + 2]
                hex_code = f"#{r:02x}{g:02x}{b:02x}"
                pct = round((count / total_pixels) * 100, 1)
                colors.append({
                    "hex": hex_code,
                    "rgb": [r, g, b],
                    "percentage": pct,
                })
            colors.sort(key=lambda c: c["percentage"], reverse=True)
        tool_logger.info(
            "extracted %d colors from %d-byte image in %.2fs",
            len(colors),
            len(image_data),
            time.monotonic() - started,
        )
        return colors


palette_extractor_service = PaletteExtractorService()
