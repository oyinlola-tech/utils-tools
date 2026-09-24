"""Per-file job status updates."""

from app.core.logging import get_tool_logger
from app.infrastructure.jobs import local_job_storage
from app.modules.jobs.services.job_file_factory import (
    fmt_size,
)
from app.modules.jobs.services.job_lock import job_metadata_lock


class JobFileStatusService:

    def update_file_status(
        self,
        job_id: str,
        file_id: str,
        status: str,
        original_size: int = 0,
        compressed_size: int = 0,
        savings_percent: float = 0,
        error: str | None = None,
        output_filename: str = "",
        download_url: str = "",
        content_type: str = "",
        output_format: str = "",
        quality: int | None = None,
        compression_preset: str = "",
        width: int | None = None,
        height: int | None = None,
        target_size_bytes: int | None = None,
        target_achieved: bool = False,
    ) -> None:
        with job_metadata_lock:
            metadata = local_job_storage.read_metadata(job_id)
            tool_id = metadata.get("tool_id", "unknown")
            tool_logger = get_tool_logger(tool_id)
            for file in metadata.get("files", []):
                if file["id"] == file_id:
                    previous_status = file["status"]
                    file["status"] = status
                    file["original_size_bytes"] = original_size
                    file["compressed_size_bytes"] = compressed_size
                    file["savings_percent"] = savings_percent
                    file["error"] = error
                    file["output_filename"] = output_filename
                    file["download_url"] = download_url
                    file["content_type"] = content_type
                    file["output_format"] = output_format
                    file["quality"] = quality
                    file["compression_preset"] = compression_preset
                    file["width"] = width
                    file["height"] = height
                    file["target_size_bytes"] = target_size_bytes
                    file["target_achieved"] = target_achieved

                    if status == "completed":
                        tool_logger.info(
                            "File %s completed for job %s: %s -> %s (%s%% saved)",
                            file.get("filename", file_id),
                            job_id,
                            fmt_size(original_size),
                            fmt_size(compressed_size),
                            savings_percent,
                        )
                    if status == "failed":
                        tool_logger.warning(
                            "File %s failed for job %s: %s",
                            file.get("filename", file_id),
                            job_id,
                            error or "no error reason",
                        )
                    if (
                        status == "completed"
                        and previous_status != "completed"
                    ):
                        metadata["completed_files"] += 1
                    if (
                        status == "failed"
                        and previous_status != "failed"
                    ):
                        metadata["failed_files"] += 1
                    break
            metadata["original_size_bytes"] = sum(
                item.get("original_size_bytes", 0)
                for item in metadata.get("files", [])
            )
            metadata["compressed_size_bytes"] = sum(
                item.get("compressed_size_bytes", 0)
                for item in metadata.get("files", [])
            )
            local_job_storage.write_metadata(job_id, metadata)


job_file_status_service = JobFileStatusService()
