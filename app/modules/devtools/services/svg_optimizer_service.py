"""SVG minification for the svg-optimizer tool."""

import re
import time
from xml.etree import ElementTree

from app.core.logging import get_tool_logger


class SvgOptimizerService:
    """Minify an SVG while keeping it structurally valid."""

    def optimize_svg(
        self,
        svg_data: bytes,
        precision: int = 2,
    ) -> dict:
        """Minify an SVG while keeping it structurally valid.

        Uses safe text-level transforms (comment strip, whitespace
        collapse, numeric rounding) and verifies the result still
        parses as XML before returning it.
        """
        tool_logger = get_tool_logger("svg-optimizer")
        started = time.monotonic()
        text = svg_data.decode("utf-8")

        try:
            ElementTree.fromstring(svg_data)
        except ElementTree.ParseError as error:
            raise ValueError(f"Invalid SVG file: {error}") from error

        minified = self._minify(text, precision)
        try:
            ElementTree.fromstring(minified.encode("utf-8"))
        except ElementTree.ParseError as error:
            raise ValueError(
                f"Minification produced invalid SVG: {error}"
            ) from error

        minified_bytes = minified.encode("utf-8")
        tool_logger.info(
            "optimized svg %d -> %d bytes (%.1f%%) in %.2fs",
            len(svg_data),
            len(minified_bytes),
            100 * (1 - len(minified_bytes) / max(1, len(svg_data))),
            time.monotonic() - started,
        )
        return {
            "data": minified_bytes,
            "original_size": len(svg_data),
            "minified_size": len(minified_bytes),
        }

    @staticmethod
    def _minify(raw: str, precision: int | None) -> str:
        cleaned = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
        cleaned = re.sub(r">\s+<", "><", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.replace(" />", "/>")
        if precision is not None and precision >= 0:
            cleaned = _ATTRIBUTE.sub(
                lambda m: SvgOptimizerService._round_attribute(m, precision),
                cleaned,
            )
        return cleaned

    @staticmethod
    def _round_attribute(match: re.Match, precision: int) -> str:
        """Round decimals only inside geometric attribute values.

        Rounding every number in the document corrupted the XML
        declaration (``version="1.0"`` -> ``"1"``, which browsers
        reject), base64 data URIs, ids and URLs.
        """
        name = match.group("name")
        if name.split(":")[-1] not in _NUMERIC_ATTRIBUTES:
            return match.group(0)
        value = _DECIMAL.sub(
            lambda m: SvgOptimizerService._round(m, precision),
            match.group("value"),
        )
        quote = match.group("quote")
        return f"{match.group('lead')}{name}={quote}{value}{quote}"

    @staticmethod
    def _round(match: re.Match, precision: int) -> str:
        text = match.group(0)
        try:
            value = round(float(text), precision)
        except (ValueError, OverflowError):
            return text
        if value == int(value):
            rounded = str(int(value))
        else:
            rounded = format(value, f".{precision}f").rstrip("0").rstrip(".")
        if rounded == "-0":
            rounded = "0"
        following = match.string[match.end():match.end() + 1]
        if "." not in rounded and following == ".":
            # "1.5.5" is two numbers; keep them apart once the first
            # loses its decimal point.
            rounded += " "
        return rounded


# Attributes whose values are purely numbers, lengths or path data.
_NUMERIC_ATTRIBUTES = {
    "d", "points", "transform", "gradientTransform", "patternTransform",
    "viewBox", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx",
    "ry", "fx", "fy", "width", "height", "stroke-width", "stroke-dasharray",
    "stroke-dashoffset", "stroke-miterlimit", "opacity", "fill-opacity",
    "stroke-opacity", "stop-opacity", "offset", "dx", "dy", "font-size",
    "letter-spacing", "stdDeviation", "refX", "refY", "markerWidth",
    "markerHeight", "k1", "k2", "k3", "k4", "scale", "radius",
}
_ATTRIBUTE = re.compile(
    r"(?P<lead>\s)(?P<name>[\w:.-]+)\s*=\s*(?P<quote>[\"'])"
    r"(?P<value>.*?)(?P=quote)",
    flags=re.DOTALL,
)
# Only numbers with a fractional part need rounding; integers are left
# untouched so nothing like leading zeros or exponents is rewritten.
_DECIMAL = re.compile(r"-?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?")


svg_optimizer_service = SvgOptimizerService()
