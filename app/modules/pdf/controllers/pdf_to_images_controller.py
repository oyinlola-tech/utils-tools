"""PDF to images conversion controller."""

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.infrastructure.archive.zip_adapter import zip_adapter
from app.modules.pdf.controllers.pdf_controller_helpers import (
    read_pdf,
)
from app.modules.pdf.pdf_repository import pdf_repository
from app.modules.pdf.pdf_schema import (
    PdfImagesResponse,
    PdfPageFile,
)
from app.modules.pdf.pdf_service import pdf_service


class PdfToImagesController:

    async def to_images(
        self,
        file: UploadFile,
        image_format: str,
        dpi: int,
        as_zip: bool = False,
    ) -> PdfImagesResponse:
        file_data, filename = await read_pdf(file)
        try:
            pages = await run_in_threadpool(
                pdf_service.to_images,
                file_data,
                image_format=image_format,
                dpi=dpi,
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to convert PDF: {error}",
            ) from error
        base_name = filename.rsplit(".", 1)[0]
        details = {
            "page_count": len(pages),
            "image_format": image_format,
            "dpi": dpi,
        }
        if as_zip:
            data = zip_adapter.create_archive(pages)
            output_path = pdf_repository.save_output_file(
                data,
                f"{base_name}-pages.zip",
            )
            return PdfImagesResponse(
                success=True,
                image_format=image_format,
                dpi=dpi,
                page_count=len(pages),
                as_zip=True,
                filename=output_path.name,
                size_bytes=len(data),
                download_url=(
                    f"/api/v1/tools/pdf/download/{output_path.name}"
                ),
                details=details,
            )
        page_files: list[PdfPageFile] = []
        for index, (page_name, page_data) in enumerate(
            pages,
            start=1,
        ):
            output_path = pdf_repository.save_output_file(
                page_data,
                page_name,
            )
            page_files.append(
                PdfPageFile(
                    filename=output_path.name,
                    size_bytes=len(page_data),
                    download_url=(
                        f"/api/v1/tools/pdf/download/"
                        f"{output_path.name}"
                    ),
                    page=index,
                )
            )
        return PdfImagesResponse(
            success=True,
            image_format=image_format,
            dpi=dpi,
            page_count=len(pages),
            as_zip=False,
            details=details,
            pages=page_files,
        )


pdf_to_images_controller = PdfToImagesController()
