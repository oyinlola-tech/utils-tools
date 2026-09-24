"""PDF watermarking service."""

import time
from io import BytesIO

import fitz

from app.core.logging import get_tool_logger


class PdfWatermarkService:

    def add_watermark(
        self,
        file_data: bytes,
        text: str = "CONFIDENTIAL",
    ) -> tuple[bytes, int]:
        tool_logger = get_tool_logger("pdf-watermark")
        started = time.monotonic()

        if not text.strip():
            raise ValueError("Watermark text cannot be empty.")

        doc = fitz.open(stream=file_data, filetype="pdf")
        total_pages = len(doc)
        for page in doc:
            rect = page.rect
            point = fitz.Point(rect.width * 0.2, rect.height * 0.65)
            page.insert_text(
                point,
                text,
                fontsize=36,
                color=(0.6, 0.6, 0.6),
                # rotate= only accepts multiples of 90; morph gives a diagonal.
                morph=(point, fitz.Matrix(45)),
            )
        output_buffer = BytesIO()
        doc.save(output_buffer)
        doc.close()
        tool_logger.info(
            "watermarked %d pages in %.2fs",
            total_pages,
            time.monotonic() - started,
        )
        return output_buffer.getvalue(), total_pages


pdf_watermark_service = PdfWatermarkService()
