"""Job-level status operations."""

from datetime import datetime, timezone

from app.core.logging import get_tool_logger
from app.infrastructure.jobs import local_job_storage
from app.modules.jobs.services.job_lock import job_metadata_lock


class JobStatusService:

    def update_status(
        self,
        job_id: str,
        status: str,
    ) -> None:
        with job_metadata_lock:
            metadata = local_job_storage.read_metadata(job_id)
            if metadata.get("status") == "cancelled" and status != "cancelled":
                # A cancelled job stays cancelled.
                return
            metadata["status"] = status
            metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
            local_job_storage.write_metadata(job_id, metadata)
        tool_id = metadata.get("tool_id", "unknown")
        get_tool_logger(tool_id).info(
            "Job %s status: %s", job_id, status
        )

    def set_download_url(
        self,
        job_id: str,
        download_url: str,
    ) -> None:
        with job_metadata_lock:
            metadata = local_job_storage.read_metadata(job_id)
            metadata["download_url"] = download_url
            local_job_storage.write_metadata(job_id, metadata)
        tool_id = metadata.get("tool_id", "unknown")
        get_tool_logger(tool_id).info(
            "Download ready for job %s", job_id
        )

    def cancel(
        self,
        job_id: str,
    ) -> None:
        with job_metadata_lock:
            metadata = local_job_storage.read_metadata(job_id)
            if not metadata:
                raise ValueError("Job not found.")
            if metadata.get("status") in {
                "completed",
                "failed",
                "cancelled",
            }:
                return
            self.update_status(job_id, "cancelled")
        tool_id = metadata.get("tool_id", "unknown")
        get_tool_logger(tool_id).info(
            "Job %s cancelled", job_id
        )

    def is_cancelled(self, job_id: str) -> bool:
        metadata = local_job_storage.read_metadata(job_id)
        return metadata.get("status") == "cancelled"


job_status_service = JobStatusService()
