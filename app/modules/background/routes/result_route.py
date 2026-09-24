"""Background job result and download endpoints."""

from fastapi import APIRouter, HTTPException

from app.api import API_PREFIX
from app.modules.background.background_repository import (
    background_repository,
)
from app.modules.background.routes.background_route_helpers import (
    background_jobs,
)
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import is_safe_filename

CONTENT_TYPE_MAP = {
    ".png": "image/png",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def create_result_router() -> APIRouter:
    router = APIRouter(
        prefix=f"{API_PREFIX}/background",
        tags=["Background Removal"],
    )

    @router.get("/result/{job_id}")
    async def get_background_result(job_id: str):
        job = background_jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Background job not found.",
            )
        return job

    @router.get("/download/{filename}")
    async def download_processed_file(
        filename: str,
    ):
        if not is_safe_filename(filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid filename",
            )
        file_path = background_repository.get_processed_file(filename)
        if not file_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Processed file not found",
            )
        media_type = CONTENT_TYPE_MAP.get(
            file_path.suffix.lower(),
            "application/octet-stream",
        )
        try:
            return download_response(file_path, media_type)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail="Processed file not found",
            ) from error

    return router
