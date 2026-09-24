from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.shared.constants.file_constants import (
    EXPECTED_EXTENSION_BY_MIME,
    MAX_FILES_PER_BATCH,
)
from app.shared.utils.image_util import ImageTooLargeError, check_pixel_limit

Image.MAX_IMAGE_PIXELS = 50_000_000


MAX_IMAGE_SIZE = 25 * 1024 * 1024
MAX_PDF_SIZE = 50 * 1024 * 1024


def validate_file_count(
    count: int,
    limit: int = MAX_FILES_PER_BATCH,
) -> None:
    if count < 1:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required.",
        )
    if count > limit:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {limit} files per request.",
        )


def extension_matches_mime(
    filename: str,
    mime_type: str,
) -> bool:
    """Cross-check the client filename extension against the detected MIME.

    The MIME type comes from magic-byte inspection and is authoritative;
    a mismatch means the client either renamed the file or is hiding its
    real content.
    """
    expected = EXPECTED_EXTENSION_BY_MIME.get(mime_type)
    if expected is None:
        return True
    actual = Path(filename).suffix.lower()
    if actual == expected:
        return True
    return bool(mime_type == "image/jpeg" and actual == ".jpeg")


def validate_filename_extension(
    filename: str,
    mime_type: str,
) -> None:
    if not extension_matches_mime(filename, mime_type):
        raise HTTPException(
            status_code=415,
            detail=(
                f"File extension '{Path(filename).suffix}' does not "
                "match the detected file content."
            ),
        )


def validate_file_size(
    file_data: bytes,
    maximum_size: int,
) -> None:
    file_size = len(file_data)
    if file_size > maximum_size:
        maximum_mb = maximum_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=(
                f"File is too large. "
                f"Maximum size is "
                f"{maximum_mb:.0f} MB."
            ),
        )


def validate_image(
    file_data: bytes,
) -> Image.Image:
    try:
        image = Image.open(BytesIO(file_data))
        # Reject by header dimensions before decoding anything: Pillow
        # only warns (rather than raising) up to 2x MAX_IMAGE_PIXELS.
        check_pixel_limit(image)
        image.verify()
        image = Image.open(BytesIO(file_data))
        image.load()
        return image
    except ImageTooLargeError:
        raise
    except Image.DecompressionBombError as error:
        raise ImageTooLargeError(
            "Image dimensions are too large to process."
        ) from error
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
    ) as error:
        raise ValueError(
            "The uploaded file is not a valid image."
        ) from error


from app.shared.file_inspection.file_inspector import (
    FileInspectionResult,
    file_inspector,
)


def inspect_and_validate(
    file_data: bytes,
) -> FileInspectionResult:
    if not file_data:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    inspection = file_inspector.inspect(file_data)

    if not inspection.is_supported:
        raise HTTPException(
            status_code=415,
            detail="This file type is not supported.",
        )

    if inspection.category.value == "image":
        validate_file_size(file_data, MAX_IMAGE_SIZE)
        try:
            validate_image(file_data)
        except ImageTooLargeError as error:
            raise HTTPException(
                status_code=413,
                detail=str(error),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
    elif inspection.category.value == "pdf":
        validate_file_size(file_data, MAX_PDF_SIZE)
        try:
            validate_pdf(file_data)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

    return inspection


def validate_pdf(
    file_data: bytes,
) -> None:
    if not file_data.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file.")
    if b"%%EOF" not in file_data[-1024:]:
        raise ValueError("PDF appears to be incomplete.")
