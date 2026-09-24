"""Background removal controller."""

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

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


class RemoveBackgroundController:

    async def remove_background(
        self,
        file: UploadFile,
        output_format: str = "webp",
    ) -> BackgroundRemovalResponse:
        file_data, filename = await read_image_upload(file)
        try:
            processed_image, width, height = (
                await run_in_threadpool(
                    background_service.remove_background,
                    file_data=file_data,
                    original_filename=filename,
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


remove_background_controller = RemoveBackgroundController()
