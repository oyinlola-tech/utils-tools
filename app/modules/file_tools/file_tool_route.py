import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api import API_PREFIX
from app.modules.file_tools.file_tool_controller import (
    file_tools_controller,
)
from app.modules.file_tools.file_tool_repository import (
    file_tool_repository,
)
from app.modules.file_tools.file_tool_schema import (
    DuplicateReport,
    FileAnalysisResponse,
    FileToolResponse,
)
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import is_safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{API_PREFIX}/tools/file",
    tags=["File Tools"],
)


@router.post("/analyze", response_model=FileAnalysisResponse)
async def analyze_files(
    files: list[UploadFile] = File(...),
):
    logger.info("analyze_files: files=%d", len(files))
    return await file_tools_controller.analyze(files)


@router.post("/zip", response_model=FileToolResponse)
async def create_zip(
    files: list[UploadFile] = File(...),
):
    logger.info("create_zip: files=%d", len(files))
    return await file_tools_controller.create_zip(files)


@router.post("/duplicates", response_model=list[DuplicateReport])
async def find_duplicates(
    files: list[UploadFile] = File(...),
):
    logger.info("find_duplicates: files=%d", len(files))
    return await file_tools_controller.find_duplicates(files)


@router.get("/download/{filename}")
async def download_output_file(
    filename: str,
):
    if not is_safe_filename(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )
    file_path = file_tool_repository.get_output_file(filename)
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output file not found",
        )
    content_types = {
        ".zip": "application/zip",
        ".pdf": "application/pdf",
    }
    media_type = content_types.get(
        file_path.suffix.lower(),
        "application/octet-stream",
    )
    return download_response(file_path, media_type)
