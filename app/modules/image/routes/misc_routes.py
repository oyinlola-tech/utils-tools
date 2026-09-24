"""Routes for the remaining image tools: metadata-remover, watermark,
palette-extractor, presets and processed-file downloads."""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.modules.image.image_repository import image_repository
from app.modules.image.image_schema import ImageToolResult
from app.modules.image.image_tools_controller import image_tools_controller
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import is_safe_filename

logger = logging.getLogger(__name__)

misc_router = APIRouter(tags=["Image Tools"])


@misc_router.post("/remove-metadata", response_model=ImageToolResult)
async def remove_metadata(file: UploadFile = File(...)):
    logger.info("remove_metadata: file=%s", file.filename)
    return await image_tools_controller.remove_metadata(file)


@misc_router.post("/watermark", response_model=ImageToolResult)
async def add_watermark(
    file: UploadFile = File(...),
    text: str | None = Form(None),
    logo: UploadFile | None = File(None),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.7, gt=0, le=1),
    size_ratio: float = Form(0.1),
    rotation: int = Form(0),
):
    logger.info(
        "add_watermark: file=%s position=%s opacity=%s size_ratio=%s rotation=%s",
        file.filename, position, opacity, size_ratio, rotation,
    )
    return await image_tools_controller.add_watermark(
        file,
        text=text,
        logo=logo,
        position=position,
        opacity=opacity,
        size_ratio=size_ratio,
        rotation=rotation,
    )


@misc_router.post("/palette-extractor")
async def extract_palette(
    file: UploadFile = File(...),
    num_colors: int = Form(6),
):
    return await image_tools_controller.extract_palette(file, num_colors=num_colors)


@misc_router.get("/social-presets")
async def social_presets():
    from app.shared.constants.social_presets import SOCIAL_PRESETS

    return {"success": True, "presets": SOCIAL_PRESETS}


@misc_router.get("/presets")
async def dimension_presets():
    from app.shared.constants.social_presets import STANDARD_PRESETS

    return {"success": True, "presets": STANDARD_PRESETS}


@misc_router.get("/download/{filename}")
async def download_processed_file(filename: str):
    if not is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = image_repository.get_processed_file(filename)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Processed file not found")
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".avif": "image/avif",
    }
    media_type = content_types.get(
        file_path.suffix.lower(),
        "application/octet-stream",
    )
    return download_response(file_path, media_type)
