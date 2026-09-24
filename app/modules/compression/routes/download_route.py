"""Compressed file download endpoint."""

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.infrastructure.jobs import local_job_storage
from app.modules.compression.compression_repository import (
    compression_repository,
)
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import (
    is_safe_filename,
)

CONTENT_TYPE_MAP = {
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".avif": "image/avif",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
}


def create_download_router() -> APIRouter:
    router = APIRouter(
        tags=["Compression"],
    )

    @router.get("/download/{filename}")
    async def download_compressed_file(
        filename: str,
    ):
        if not is_safe_filename(filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid filename",
            )
        file_path = compression_repository.get(filename)
        blob_key = None
        if not file_path.is_file():
            file_path = local_job_storage.materialize_download(filename)
            blob_key = f"downloads/{filename}"
        if not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Compressed file not found",
            )
        extension = file_path.suffix.lower()
        content_type = CONTENT_TYPE_MAP.get(
            extension,
            "application/octet-stream",
        )
        try:
            return download_response(
                file_path,
                content_type,
                blob_key=blob_key,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="Compressed file not found",
            ) from error

    return router
