"""Shared PDF controller helpers."""

from io import BytesIO

import pikepdf
from fastapi import HTTPException, UploadFile

from app.modules.pdf.pdf_repository import pdf_repository
from app.modules.pdf.pdf_schema import (
    PdfToolResponse,
)
from app.shared.file_inspection.file_validation import (
    inspect_and_validate,
)


async def read_pdf(
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
    if inspection.category.value != "pdf":
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are supported",
        )
    ensure_pdf_readable(file_data, file.filename)
    return file_data, file.filename


def ensure_pdf_readable(file_data: bytes, filename: str) -> None:
    """Reject password-protected or unparseable PDFs with a clear 400.

    pikepdf raises ``PasswordError``/``PdfError`` (not ValueError), which
    previously escaped every PDF controller as a 500. PDFs that only
    carry an owner password (no password needed to open) still pass.
    """
    try:
        with pikepdf.open(BytesIO(file_data)):
            pass
    except pikepdf.PasswordError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{filename} is password-protected. "
                "Remove the password and try again."
            ),
        ) from error
    except (pikepdf.PdfError, ValueError, OSError) as error:
        raise HTTPException(
            status_code=400,
            detail=f"{filename} is damaged or is not a valid PDF.",
        ) from error


def save_output(
    data: bytes,
    filename: str,
    details: dict | None = None,
) -> PdfToolResponse:
    output_path = pdf_repository.save_output_file(
        data,
        filename,
    )
    return PdfToolResponse(
        success=True,
        filename=output_path.name,
        size_bytes=len(data),
        download_url=f"/api/v1/tools/pdf/download/{output_path.name}",
        details=details or {},
    )


def http_error(action: str):
    def raise_error(error: Exception) -> None:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to {action}: {error}",
        ) from error

    return raise_error
