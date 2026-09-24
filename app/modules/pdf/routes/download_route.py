"""PDF output download route."""

from fastapi import APIRouter, HTTPException

from app.api import API_PREFIX
from app.modules.pdf.pdf_repository import pdf_repository
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import is_safe_filename

CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def create_download_router() -> APIRouter:
    router = APIRouter(
        prefix=f"{API_PREFIX}/tools/pdf",
        tags=["PDF Tools"],
    )

    @router.get("/download/{filename}")
    async def download_output_file(
        filename: str,
    ):
        if not is_safe_filename(filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid filename",
            )
        file_path = pdf_repository.get_output_file(filename)
        if not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Output file not found",
            )
        media_type = CONTENT_TYPE_MAP.get(
            file_path.suffix.lower(),
            "application/octet-stream",
        )
        return download_response(file_path, media_type)

    return router
