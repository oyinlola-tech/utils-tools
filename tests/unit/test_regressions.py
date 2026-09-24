import pytest

from app.infrastructure.storage import storage
from app.modules.background.background_repository import background_repository
from app.modules.compression.batch_compression_service import BatchCompressionService
from app.modules.compression.compression_repository import compression_repository
from app.modules.jobs.job_service import job_service


def test_repository_rejects_traversal_filenames():
    with pytest.raises(ValueError):
        compression_repository.save(b"payload", "../../etc/passwd")

    # Output names derived from uploads are sanitized to a basename
    # rather than rejected, so they can never escape the output dir.
    saved = background_repository.save_processed_file(
        b"payload", "../../etc/passwd"
    )
    try:
        assert saved.parent == storage.processed_path.resolve()
        assert saved.name.startswith("passwd_")
    finally:
        storage.delete(saved)


def test_cancelled_job_is_finalized_as_cancelled():
    job_id = job_service.create(["a.txt", "b.txt"])
    job_service.update_status(job_id, "processing")
    job_service.update_file_status(job_id, "0", "processing")
    job_service.update_file_status(job_id, "1", "processing")
    job_service.update_status(job_id, "cancelled")

    BatchCompressionService()._finalize_job(job_id)

    assert job_service.get(job_id)["status"] == "cancelled"
