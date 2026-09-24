"""Routes for the favicon-generator tool."""

import logging
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.modules.devtools.dev_tools_controller import dev_tools_controller

logger = logging.getLogger(__name__)

favicon_router = APIRouter(tags=["Developer Tools"])


@favicon_router.post("/favicon")
async def generate_favicon(
    image: UploadFile = File(...),
    size: int = Form(64),
    add_padding: bool = Form(False),
):
    logger.info(
        "generate_favicon: image=%s size=%d padding=%s",
        image.filename, size, add_padding,
    )
    result = await dev_tools_controller.favicon(
        image,
        size=size,
        add_padding=add_padding,
    )

    archive_buffer = BytesIO()
    with ZipFile(
        archive_buffer,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for item, data in [
            ("favicon.ico", result["ico"]),
            (
                # Named after the PNG's real size; sizes[-1] is the
                # largest ICO frame (48 when a 16/32 px PNG was chosen).
                f"favicon-{result['png_size']}x{result['png_size']}.png",
                result["png"],
            ),
        ]:
            archive.writestr(item, data)
    headers = {"Content-Disposition": "attachment; filename=favicon-set.zip"}
    return Response(
        content=archive_buffer.getvalue(),
        media_type="application/zip",
        headers=headers,
    )
