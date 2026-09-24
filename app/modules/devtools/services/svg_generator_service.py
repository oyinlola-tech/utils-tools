"""Raster-to-SVG tracing for the svg-generator tool."""

import time

from app.core.logging import get_tool_logger
from app.shared.utils.image_util import load_image


class SvgGeneratorService:
    """Trace a raster image into a single-path SVG."""

    def generate_svg(
        self,
        image_data: bytes,
        threshold: int = 128,
        background_color: str = "white",
        foreground_color: str = "black",
    ) -> str:
        """Convert a raster image (PNG/JPG/WebP) to an SVG path.

        Uses potrace to trace the bitmap and produces a single
        ``<path>`` element per contiguous shape. The image is
        converted to 1-bit black-and-white before tracing.
        """
        tool_logger = get_tool_logger("svg-generator")
        started = time.monotonic()
        import numpy as np
        import potrace

        source = load_image(image_data)
        grayscale = source.convert("L")
        bw = grayscale.point(lambda x: 0 if x < threshold else 255, mode="1")
        bitmap = potrace.Bitmap(np.array(bw))
        path = bitmap.trace()

        w, h = source.width, source.height
        parts: list[str] = [
            '<svg xmlns="http://www.w3.org/2000/svg"',
            f' width="{w}" height="{h}"',
            f' viewBox="0 0 {w} {h}">',
        ]
        if background_color.lower() != "transparent":
            parts.append(
                f'<rect width="{w}" height="{h}" fill="{background_color}"/>'
            )
        for curve in path:
            start = curve.start_point
            d = [f"M{start.x:.2f},{start.y:.2f}"]
            for seg in curve:
                end = seg.end_point
                if seg.is_corner:
                    d.append(f"L{end.x:.2f},{end.y:.2f}")
                else:
                    d.append(
                        f"C{seg.c1.x:.2f},{seg.c1.y:.2f} "
                        f"{seg.c2.x:.2f},{seg.c2.y:.2f} {end.x:.2f},{end.y:.2f}"
                    )
            d.append("Z")
            parts.append(f'<path fill="{foreground_color}" d="{" ".join(d)}"/>')
        parts.append("</svg>")
        result = "".join(parts)
        tool_logger.info(
            "traced %dx%d image to %d svg paths (%d bytes) in %.2fs",
            w,
            h,
            len(path),
            len(result.encode("utf-8")),
            time.monotonic() - started,
        )
        return result


svg_generator_service = SvgGeneratorService()
