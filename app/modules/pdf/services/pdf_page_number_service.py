"""PDF page-numbering service."""

import time
from io import BytesIO

import fitz

from app.core.logging import get_tool_logger

_POSITIONS = {
    "bottom-right",
    "bottom-center",
    "bottom-left",
    "top-right",
    "top-center",
    "top-left",
}


class PdfPageNumberService:

    def add_page_numbers(
        self,
        file_data: bytes,
        position: str = "bottom-right",
    ) -> tuple[bytes, int]:
        tool_logger = get_tool_logger("pdf-page-number")
        started = time.monotonic()
        if position not in _POSITIONS:
            raise ValueError(
                "Position must be one of: " + ", ".join(sorted(_POSITIONS)) + "."
            )

        doc = fitz.open(stream=file_data, filetype="pdf")
        total_pages = len(doc)
        for page_idx in range(total_pages):
            page = doc[page_idx]
            rect = page.rect
            text = f"Page {page_idx + 1} of {total_pages}"
            y = rect.height - 25 if "bottom" in position else 30
            if "right" in position:
                x = rect.width - 100
            elif "center" in position:
                x = (rect.width / 2) - 40
            else:
                x = 40
            page.insert_text((x, y), text, fontsize=10, color=(0.2, 0.2, 0.2))
        output_buffer = BytesIO()
        doc.save(output_buffer)
        doc.close()
        tool_logger.info(
            "numbered %d pages (%s) in %.2fs",
            total_pages,
            position,
            time.monotonic() - started,
        )
        return output_buffer.getvalue(), total_pages


pdf_page_number_service = PdfPageNumberService()
