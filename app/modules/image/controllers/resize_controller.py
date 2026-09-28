"""Simple single-image resize logic for the image-resizer tool."""

from fastapi import HTTPException, UploadFile

from app.modules.image.controllers.image_controller_helpers import (
    build_result,
    read_image,
)
from app.modules.image.image_schema import ImageToolResult
from app.modules.image.services.image_helpers import SUPPORTED_CONVERSION_FORMATS
from app.modules.image.services.resizer_service import image_resizer_service


class ResizeController:
    """Resize a single image with inferred mode."""

    async def resize(
        self,
        file: UploadFile,
        width: int | None = None,
        height: int | None = None,
        percent: float | None = None,
        max_dimension: int | None = None,
        output_format: str = "png",
        cover: bool = False,
    ) -> ImageToolResult:
        file_data, filename = await read_image(file)
        normalized = output_format.lower()
        if normalized not in SUPPORTED_CONVERSION_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="Output format must be jpg, png, webp or avif.",
            )

        resize_mode, resize_kwargs = self._infer_mode(
            width, height, percent, max_dimension
        )

        try:
            result = image_resizer_service.resize(
                file_data,
                resize_mode=resize_mode,
                output_format=normalized,
                allow_upscale=cover,
                cover=cover,
                **resize_kwargs,
            )
            return build_result(filename, result)
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to resize image: {error}",
            ) from error

    @staticmethod
    def _infer_mode(
        width: int | None,
        height: int | None,
        percent: float | None,
        max_dimension: int | None,
    ) -> tuple[str, dict]:
        if percent is not None:
            return "percent", {"percent": percent}
        if width is not None and height is not None:
            return "exact", {
                "width": width,
                "height": height,
                "maintain_aspect_ratio": False,
            }
        if max_dimension is not None:
            return "max", {"max_dimension": max_dimension}
        if width is not None:
            return "aspect", {"width": width}
        if height is not None:
            return "aspect", {"height": height}
        raise HTTPException(
            status_code=400,
            detail="Provide width, height, percentage or max dimension.",
        )


resize_controller = ResizeController()
