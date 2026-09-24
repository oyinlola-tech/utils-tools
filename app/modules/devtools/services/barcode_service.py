"""Barcode generation for the barcode-generator tool."""

import time
from io import BytesIO

from app.core.logging import get_tool_logger
from app.modules.devtools.services.devtools_helpers import barcode_factory


class BarcodeService:
    """Generate barcodes in png, webp or svg."""

    def generate_barcode(
        self,
        content: str,
        code_type: str = "code128",
        output_format: str = "png",
    ) -> tuple[bytes, str]:
        tool_logger = get_tool_logger("barcode-generator")
        started = time.monotonic()
        if not content.strip():
            raise ValueError("Barcode content cannot be empty.")
        if len(content) > 200:
            raise ValueError("Barcode content must be 200 characters or fewer.")
        output_format = (output_format or "png").lower()
        if output_format not in {"png", "webp", "svg"}:
            raise ValueError("Output format must be png, webp or svg.")
        cls = barcode_factory(code_type)
        writer_options = {
            "module_width": 0.4,
            "module_height": 20,
            "font_size": 14,
            "text_distance": 3,
            "quiet_zone": 6,
        }
        if output_format == "svg":
            return self._render_svg(
                cls, content, code_type, writer_options, started, tool_logger
            )

        from barcode.writer import ImageWriter

        try:
            instance = cls(content, writer=ImageWriter())
            image = instance.render(writer_options=writer_options)
        except Exception as error:
            raise ValueError(f"Unable to render barcode: {error}") from error

        buffer = BytesIO()
        if output_format == "webp":
            image.convert("RGB").save(buffer, format="WEBP", quality=95)
            tool_logger.info(
                "generated %s barcode (webp, %d bytes) in %.2fs",
                code_type,
                buffer.getbuffer().nbytes,
                time.monotonic() - started,
            )
            return buffer.getvalue(), "image/webp"
        image.save(buffer, format="PNG")
        tool_logger.info(
            "generated %s barcode (png, %d bytes) in %.2fs",
            code_type,
            buffer.getbuffer().nbytes,
            time.monotonic() - started,
        )
        return buffer.getvalue(), "image/png"

    @staticmethod
    def _render_svg(
        cls,
        content: str,
        code_type: str,
        writer_options: dict,
        started: float,
        tool_logger,
    ) -> tuple[bytes, str]:
        from barcode.writer import SVGWriter

        try:
            instance = cls(content, writer=SVGWriter())
            data = instance.render(
                writer_options={**writer_options, "write_text": True}
            )
        except Exception as error:
            raise ValueError(
                f"Unable to encode '{content}' as {code_type}: {error}"
            ) from error
        tool_logger.info(
            "generated %s barcode (svg, %d bytes) in %.2fs",
            code_type,
            len(data),
            time.monotonic() - started,
        )
        return data, "image/svg+xml"


barcode_service = BarcodeService()
