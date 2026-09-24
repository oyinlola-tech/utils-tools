"""HTTP-facing logic for the favicon-generator tool."""

from fastapi import UploadFile

from app.modules.devtools.controllers.devtools_controller_helpers import (
    as_http_error,
    read_upload,
)
from app.modules.devtools.services.favicon_service import favicon_service


class FaviconController:
    async def favicon(
        self,
        image: UploadFile,
        size: int = 64,
        add_padding: bool = False,
    ) -> dict:
        image_data = await read_upload(image, "image")
        try:
            result = favicon_service.generate_favicon(
                image_data,
                size=size,
                add_padding=add_padding,
            )
        except (OSError, ValueError) as error:
            raise as_http_error("Unable to generate favicon", error) from error
        return {
            "success": True,
            "sizes": result["sizes"],
            "png_size": result["png_size"],
            "ico": result["ico"],
            "png": result["png"],
        }


favicon_controller = FaviconController()
