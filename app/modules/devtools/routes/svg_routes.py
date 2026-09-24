"""Routes for the svg-optimizer and svg-generator tools."""

import logging

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.core.capabilities import capability_registry
from app.modules.devtools.dev_tools_controller import dev_tools_controller
from app.shared.utils.file_util import sanitize_filename

logger = logging.getLogger(__name__)

svg_router = APIRouter(tags=["Developer Tools"])


def _check_svg_capability() -> None:
    if not capability_registry.is_available("svg-generator"):
        raise HTTPException(
            status_code=503,
            detail="SVG generation is unavailable in the current environment.",
        )


@svg_router.post("/svg-optimize")
async def optimize_svg(
    file: UploadFile = File(...),
    precision: int = Form(2),
):
    logger.info("optimize_svg: file=%s precision=%d", file.filename, precision)
    if not -1 <= precision <= 8:
        raise HTTPException(
            status_code=400,
            detail="Precision must be between 0 and 8, or -1 to keep numbers as-is.",
        )
    result = await dev_tools_controller.optimize_svg(file, precision=precision)
    stem = sanitize_filename(file.filename or "", fallback="optimized")
    stem = stem.rsplit(".", 1)[0] if stem.lower().endswith(".svg") else stem
    headers = {
        "Content-Disposition": f'attachment; filename="{stem}.min.svg"'
    }
    return Response(
        content=result["data"],
        media_type="image/svg+xml",
        headers=headers,
    )


@svg_router.post("/svg-generate")
async def generate_svg(
    image: UploadFile = File(...),
    threshold: int = Form(128),
    background_color: str = Form("white"),
    foreground_color: str = Form("black"),
):
    _check_svg_capability()
    logger.info("generate_svg: image=%s threshold=%d", image.filename, threshold)
    data, content_type = await dev_tools_controller.svg(
        image,
        threshold=threshold,
        background_color=background_color,
        foreground_color=foreground_color,
    )
    headers = {"Content-Disposition": "attachment; filename=converted.svg"}
    return Response(
        content=data,
        media_type=content_type,
        headers=headers,
    )
