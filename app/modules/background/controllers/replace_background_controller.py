"""Background replacement controller."""

from fastapi import HTTPException, UploadFile

from app.modules.background.background_schema import (
    BackgroundRemovalResponse,
)
from app.modules.background.background_service import (
    background_service,
)
from app.modules.background.controllers.background_controller_helpers import (
    read_image_upload,
    save_processed,
)


class ReplaceBackgroundController:

    async def replace_background(
        self,
        file: UploadFile,
        color: str | None = None,
        background_image: UploadFile | None = None,
        blur: int = 0,
        output_format: str = "png",
    ) -> BackgroundRemovalResponse:
        file_data, filename = await read_image_upload(file)
        background_data = None
        if background_image is not None:
            background_data = await background_image.read()
        if not color and not background_data and blur <= 0:
            raise HTTPException(
                status_code=400,
                detail="Provide a background color, image or blur amount.",
            )
        try:
            processed_image, width, height = (
                background_service.replace_background(
                    file_data=file_data,
                    color=color,
                    image_data=background_data,
                    blur=blur,
                )
            )
            output_name, size_bytes = save_processed(
                processed_image,
                output_format,
                filename,
            )
            return {
                "success": True,
                "original_filename": filename,
                "width": width,
                "height": height,
                "format": output_format,
                "filename": output_name,
                "size_bytes": size_bytes,
                "download_url": f"/api/v1/background/download/{output_name}",
            }
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to process image: {error}",
            ) from error


replace_background_controller = ReplaceBackgroundController()
