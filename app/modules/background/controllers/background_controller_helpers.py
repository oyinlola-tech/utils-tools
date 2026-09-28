"""Shared background controller helpers."""

from io import BytesIO

from fastapi import HTTPException, UploadFile

from app.modules.background.background_repository import (
    background_repository,
)
from app.shared.file_inspection.file_validation import (
    inspect_and_validate,
)


async def read_image_upload(
    file: UploadFile,
) -> tuple[bytes, str]:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )
    file_data = await file.read()
    if not file_data:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )
    inspection = inspect_and_validate(file_data)
    if inspection.category.value != "image":
        raise HTTPException(
            status_code=415,
            detail="Only image files are supported",
        )
    return file_data, file.filename


def encode_output(
    processed_image,
    output_format: str,
) -> tuple[bytes, str]:
    output_buffer = BytesIO()
    if output_format == "png":
        processed_image.save(output_buffer, format="PNG")
        extension = ".png"
    else:
        processed_image.save(
            output_buffer,
            format="WEBP",
            quality=95,
            # Method 6 takes many times longer on images with transparency,
            # which is every image this tool produces.
            method=4,
        )
        extension = ".webp"
    return output_buffer.getvalue(), extension


def save_processed(
    processed_image,
    output_format: str,
    original_filename: str,
) -> tuple[str, int]:
    final_data, extension = encode_output(
        processed_image,
        output_format,
    )
    output_filename = original_filename.rsplit(".", 1)[0] + extension
    output_path = background_repository.save_processed_file(
        final_data,
        output_filename,
    )
    return output_path.name, len(final_data)
