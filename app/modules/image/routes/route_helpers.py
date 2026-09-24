"""Shared validation helpers for the image tool routes."""

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.modules.image.services.image_helpers import SUPPORTED_CONVERSION_FORMATS


def validate_batch_files(files: list[UploadFile]) -> None:
    """Reject empty or oversized batches."""
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Too many files. Maximum is 50.")


def validate_quality(quality: int | None) -> None:
    if quality is not None and (quality < 1 or quality > 100):
        raise HTTPException(status_code=400, detail="Quality must be between 1 and 100.")


def is_valid_color(value: str) -> bool:
    """Whether Pillow can use ``value`` as a fill colour.

    ``_parse_color`` passes unknown strings through unchanged (it never
    raises), so this used to accept anything and the error only surfaced
    per file, as a failure inside a 200 response.
    """
    from PIL import ImageColor

    from app.infrastructure.compression.pillow_adapter import _parse_color

    parsed = _parse_color(value)
    if isinstance(parsed, tuple):
        return True
    try:
        ImageColor.getrgb(str(parsed))
        return True
    except (ValueError, OSError):
        return False


def validate_background_color(background_color: str | None) -> None:
    if background_color is not None and not is_valid_color(background_color):
        raise HTTPException(status_code=400, detail="Invalid background color.")


def validate_conversion_format(output_format: str) -> None:
    if output_format.lower() not in SUPPORTED_CONVERSION_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Output format must be jpg, png, webp or avif.",
        )


def validate_resize_params(
    resize_mode: str,
    width: int | None,
    height: int | None,
    percent: float | None,
    max_width: int | None,
    max_height: int | None,
    quality: int | None,
    output_format: str,
    background_color: str | None,
) -> None:
    """Validate resize mode, dimensions, quality, format and color."""
    if resize_mode not in {"aspect", "exact", "percent", "max"}:
        raise HTTPException(
            status_code=400,
            detail="Resize mode must be aspect, exact, percent or max.",
        )
    if width is not None and width <= 0:
        raise HTTPException(status_code=400, detail="Width must be positive.")
    if height is not None and height <= 0:
        raise HTTPException(status_code=400, detail="Height must be positive.")
    if max_width is not None and max_width <= 0:
        raise HTTPException(status_code=400, detail="Maximum width must be positive.")
    if max_height is not None and max_height <= 0:
        raise HTTPException(status_code=400, detail="Maximum height must be positive.")
    if resize_mode == "percent" and (percent is None or percent <= 0):
        raise HTTPException(
            status_code=400,
            detail="Percentage must be greater than zero.",
        )
    if resize_mode in ("aspect", "exact") and width is None and height is None:
        raise HTTPException(
            status_code=400,
            detail="Provide width and/or height for this resize mode.",
        )
    if resize_mode == "max" and max_width is None and max_height is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least a maximum width or height.",
        )
    validate_quality(quality)
    if width is not None and width > settings.max_image_width:
        raise HTTPException(
            status_code=400,
            detail=f"Width exceeds the maximum of {settings.max_image_width} pixels.",
        )
    if height is not None and height > settings.max_image_height:
        raise HTTPException(
            status_code=400,
            detail=f"Height exceeds the maximum of {settings.max_image_height} pixels.",
        )
    if max_width is not None and max_width > settings.max_image_width:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum width exceeds the maximum of {settings.max_image_width} pixels.",
        )
    if max_height is not None and max_height > settings.max_image_height:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum height exceeds the maximum of {settings.max_image_height} pixels.",
        )
    if (
        output_format != "auto"
        and output_format.lower() not in {"jpg", "jpeg", "png", "webp"}
    ):
        raise HTTPException(
            status_code=400,
            detail="Output format must be auto, jpg, png, webp, or avif.",
        )
    validate_background_color(background_color)
