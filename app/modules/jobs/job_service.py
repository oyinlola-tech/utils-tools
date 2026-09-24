"""Facade over the per-tool job services."""

import copy

from app.core.logging import get_tool_logger
from app.infrastructure.jobs import local_job_storage
from app.modules.jobs.services.job_file_factory import (
    build_file_entry,
)
from app.modules.jobs.services.job_file_status_service import (
    job_file_status_service,
)
from app.modules.jobs.services.job_lock import job_metadata_lock
from app.modules.jobs.services.job_status_service import (
    job_status_service,
)


class JobService:

    def create(
        self,
        filenames: list[str],
        tool_id: str = "unknown",
    ) -> str:
        job_id = local_job_storage.create_job()
        files = [
            build_file_entry(index, filename)
            for index, filename in enumerate(filenames)
        ]
        metadata = local_job_storage.read_metadata(job_id)
        metadata.update(
            {
                "status": "created",
                "tool_id": tool_id,
                "total_files": len(files),
                "completed_files": 0,
                "failed_files": 0,
                "original_size_bytes": 0,
                "compressed_size_bytes": 0,
                "files": files,
                "download_url": None,
            }
        )
        local_job_storage.write_metadata(job_id, metadata)

        get_tool_logger(tool_id).info(
            "Job created: job_id=%s, files=%d",
            job_id,
            len(files),
        )
        return job_id

    def set_input_filename(
        self,
        job_id: str,
        file_id: str,
        input_filename: str,
    ) -> None:
        with job_metadata_lock:
            metadata = local_job_storage.read_metadata(job_id)
            for file in metadata.get("files", []):
                if file["id"] == file_id:
                    file["input_filename"] = input_filename
                    break
            local_job_storage.write_metadata(job_id, metadata)

    def update_status(
        self,
        job_id: str,
        status: str,
    ) -> None:
        job_status_service.update_status(job_id, status)

    def update_file_status(
        self,
        job_id: str,
        file_id: str,
        status: str,
        **kwargs,
    ) -> None:
        job_file_status_service.update_file_status(
            job_id,
            file_id,
            status,
            **kwargs,
        )

    def set_download_url(
        self,
        job_id: str,
        download_url: str,
    ) -> None:
        job_status_service.set_download_url(job_id, download_url)

    def get(self, job_id: str) -> dict:
        metadata = local_job_storage.read_metadata(job_id)
        return copy.deepcopy(metadata)

    def delete(self, job_id: str) -> None:
        local_job_storage.delete_job(job_id)

    def cancel(self, job_id: str) -> None:
        job_status_service.cancel(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        return job_status_service.is_cancelled(job_id)


job_service = JobService()
