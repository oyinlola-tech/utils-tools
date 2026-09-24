"""File-upload and job-storage helper for compression jobs."""

import logging
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.infrastructure.jobs import local_job_storage
from app.modules.compression.batch_compression_service import (
    batch_compression_service,
)
from app.modules.compression.image_compression.image_compression_settings import (
    PRESETS,
)
from app.modules.jobs.job_service import (
    job_service,
)
from app.shared.constants.file_constants import MAX_FILES_PER_BATCH
from app.shared.utils.file_util import (
    generate_filename,
)

logger = logging.getLogger(__name__)

_OUTPUT_FORMATS = {"auto": "auto", "webp": "webp", "png": "png", "jpeg": "jpeg", "jpg": "jpeg"}


def _validate_options(
    image_output_format: str,
    compression_preset: str,
    max_dimension: int | None,
    target_size_kb: int | None,
) -> tuple[str, str]:
    """Reject bad options before a job is created.

    Previously they were accepted with a 200 and every file then failed
    inside the background job (or, for "jpg", the encoder rejected the
    alias it did not know).
    """
    output_format = _OUTPUT_FORMATS.get((image_output_format or "").lower())
    if output_format is None:
        raise HTTPException(
            status_code=400,
            detail="Output format must be auto, webp, jpeg or png.",
        )
    preset = (compression_preset or "").lower()
    if preset not in PRESETS:
        raise HTTPException(
            status_code=400,
            detail="Compression preset must be best_quality, balanced or smallest.",
        )
    if max_dimension is not None and not 16 <= max_dimension <= 20000:
        raise HTTPException(
            status_code=400,
            detail="Maximum dimension must be between 16 and 20000 pixels.",
        )
    if target_size_kb is not None and target_size_kb < 1:
        raise HTTPException(
            status_code=400,
            detail="Target size must be at least 1 KB.",
        )
    return output_format, preset


async def start_compression(
    background_tasks: BackgroundTasks,
    files: list[UploadFile],
    image_output_format: str,
    compression_preset: str,
    max_dimension: int | None = None,
    target_size_kb: int | None = None,
    strip_metadata: bool = True,
    quality: int | None = None,
    tool_id: str = "unknown",
) -> dict:
    image_output_format, compression_preset = _validate_options(
        image_output_format,
        compression_preset,
        max_dimension,
        target_size_kb,
    )

    if not files:
        logger.warning("Compression request rejected: no files uploaded")
        raise HTTPException(
            status_code=400,
            detail="No files were uploaded.",
        )

    if len(files) > MAX_FILES_PER_BATCH:
        logger.warning(
            "Compression request rejected: %s files exceed limit of %s",
            len(files),
            MAX_FILES_PER_BATCH,
        )
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_FILES_PER_BATCH} files.",
        )

    job_id = job_service.create(
        [file.filename or "file" for file in files],
        tool_id=tool_id,
    )

    stored_files = []

    try:
        for index, file in enumerate(files):

            original_filename = file.filename or "file"

            extension = Path(original_filename).suffix.lower().lstrip(".")

            stored_filename = generate_filename(
                original_filename,
                extension=extension,
            )

            buffer = bytearray()
            total_size = 0

            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                buffer.extend(chunk)
                total_size += len(chunk)

                if total_size > (50 * 1024 * 1024):
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"{original_filename} is larger than the "
                            "50 MB upload limit."
                        ),
                    )

            local_job_storage.save_input(
                job_id,
                stored_filename,
                bytes(buffer),
            )

            file_id = str(index)

            job_service.set_input_filename(
                job_id,
                file_id,
                stored_filename,
            )

            stored_files.append(
                {
                    "id": file_id,
                    "filename": original_filename,
                    "input_filename": stored_filename,
                }
            )

        background_tasks.add_task(
            batch_compression_service.process,
            job_id,
            stored_files,
            image_output_format,
            compression_preset,
            max_dimension,
            target_size_kb,
            strip_metadata,
            quality,
        )

        logger.info(
            "Image compression job created: job_id=%s, files=%s, format=%s, preset=%s, quality=%s",
            job_id,
            len(stored_files),
            image_output_format,
            compression_preset,
            quality,
        )

    except Exception as error:
        logger.exception(
            "Failed to create compression job %s: %s",
            job_id,
            error,
        )
        job_service.cancel(job_id)

        raise

    return {
        "success": True,
        "job_id": job_id,
        "status": "created",
    }
