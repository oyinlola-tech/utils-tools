"""PDF watermarking route."""

from fastapi import APIRouter, File, Form, UploadFile

from app.api import API_PREFIX
from app.modules.pdf.pdf_controller import pdf_controller
from app.modules.pdf.pdf_schema import (
    PdfToolResponse,
)


def create_watermark_router() -> APIRouter:
    router = APIRouter(
        prefix=f"{API_PREFIX}/tools/pdf",
        tags=["PDF Tools"],
    )

    @router.post("/watermark", response_model=PdfToolResponse)
    async def watermark_pdf(
        file: UploadFile = File(...),
        text: str = Form("CONFIDENTIAL", max_length=200),
    ):
        return await pdf_controller.watermark(file, text=text)

    return router
