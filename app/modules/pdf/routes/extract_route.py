"""PDF page extraction route."""

import logging

from fastapi import APIRouter, File, Form, UploadFile

from app.api import API_PREFIX
from app.modules.pdf.pdf_controller import pdf_controller
from app.modules.pdf.pdf_schema import (
    PdfToolResponse,
)

logger = logging.getLogger(__name__)


def create_extract_router() -> APIRouter:
    router = APIRouter(
        prefix=f"{API_PREFIX}/tools/pdf",
        tags=["PDF Tools"],
    )

    @router.post("/extract", response_model=PdfToolResponse)
    async def extract_pdf_pages(
        file: UploadFile = File(...),
        pages: str = Form("all"),
    ):
        logger.info("extract_pdf_pages: file=%s pages=%s", file.filename, pages)
        return await pdf_controller.extract_pages(
            file,
            pages_spec=pages,
        )

    return router
