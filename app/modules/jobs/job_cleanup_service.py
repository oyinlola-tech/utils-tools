import logging
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.infrastructure.jobs import local_job_storage
from app.infrastructure.storage import storage

logger = logging.getLogger(__name__)

# How often a request may trigger a sweep (per process / instance).
SWEEP_INTERVAL_SECONDS = 300
# Blob prefixes holding tool outputs and job data (mirrors the local layout).
_BLOB_PREFIXES = (
    "processed/",
    "compressed/",
    "uploads/",
    "temp/",
    "jobs/",
    "downloads/",
)


def _newest_mtime(path: Path) -> float:
    newest = path.stat().st_mtime
    if path.is_dir():
        for child in path.rglob("*"):
            try:
                newest = max(newest, child.stat().st_mtime)
            except OSError:
                continue
    return newest


def sweep_directory(directory: Path, max_age_seconds: float) -> int:
    """Delete files/subdirectories not modified within ``max_age_seconds``."""
    if not directory.is_dir():
        return 0
    cutoff = time.time() - max_age_seconds
    removed = 0
    for entry in directory.iterdir():
        if entry.name.startswith("."):
            # .gitkeep and similar placeholders are not tool outputs.
            continue
        try:
            if _newest_mtime(entry) >= cutoff:
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
            removed += 1
        except OSError:
            continue
    return removed


class JobCleanupService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_sweep = 0.0
        self._running = False

    def cleanup_expired_jobs(self) -> int:
        if settings.storage_driver == "vercel":
            # Metadata lives in Blob; only the local /tmp mirror is swept
            # here (by age) and Blob itself in cleanup_expired_blobs().
            return sweep_directory(
                local_job_storage.root_path,
                settings.job_ttl_minutes * 60,
            )
        now = datetime.now(timezone.utc)
        expiration = timedelta(
            minutes=settings.job_ttl_minutes
        )
        removed = 0
        if not local_job_storage.root_path.exists():
            return 0
        for job_path in (
            local_job_storage.root_path.iterdir()
        ):
            if not job_path.is_dir():
                continue
            metadata_path = (
                job_path / "metadata.json"
            )
            if not metadata_path.exists():
                shutil.rmtree(
                    job_path,
                    ignore_errors=True,
                )
                removed += 1
                continue
            try:
                metadata = (
                    local_job_storage.read_metadata(
                        job_path.name
                    )
                )
                timestamp = (
                    metadata.get("updated_at")
                    or metadata.get("created_at")
                )
                if not timestamp:
                    shutil.rmtree(
                        job_path,
                        ignore_errors=True,
                    )
                    removed += 1
                    continue
                updated_at = datetime.fromisoformat(
                    timestamp
                )
                if (
                    now - updated_at
                    > expiration
                ):
                    shutil.rmtree(
                        job_path,
                        ignore_errors=True,
                    )
                    removed += 1
            except (
                KeyError,
                ValueError,
                OSError,
            ):
                shutil.rmtree(
                    job_path,
                    ignore_errors=True,
                )
                removed += 1
        return removed

    def cleanup_expired_downloads(
        self,
    ) -> int:
        if settings.storage_driver == "vercel":
            return sweep_directory(
                local_job_storage.download_path,
                settings.job_ttl_minutes * 60,
            )
        now = datetime.now(timezone.utc)
        expiration = timedelta(
            minutes=settings.job_ttl_minutes
        )
        removed = 0
        if not local_job_storage.download_path.exists():
            return 0
        for file_path in (
            local_job_storage.download_path.iterdir()
        ):
            if not file_path.is_file():
                continue
            try:
                modified_at = (
                    datetime.fromtimestamp(
                        file_path.stat().st_mtime,
                        tz=timezone.utc,
                    )
                )
                if (
                    now - modified_at
                    > expiration
                ):
                    file_path.unlink(
                        missing_ok=True
                    )
                    removed += 1
            except OSError:
                removed += 1
        return removed

    def cleanup_expired_outputs(self) -> int:
        """Sweep tool outputs, which previously accumulated forever.

        processed/ (every single-file tool, TTS, video), compressed/,
        uploads/ and temp/ were never cleaned, locally or in the Vercel
        /tmp mirror.
        """
        max_age = settings.job_ttl_minutes * 60
        return sum(
            sweep_directory(Path(directory), max_age)
            for directory in (
                storage.processed_path,
                storage.compressed_path,
                storage.upload_path,
                storage.temp_path,
            )
        )

    def cleanup_expired_blobs(self) -> int:
        """Delete expired objects from Vercel Blob (no-op locally)."""
        if settings.storage_driver != "vercel":
            return 0
        from vercel.blob import delete, iter_objects

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.job_ttl_minutes
        )
        expired: list[str] = []
        for prefix in _BLOB_PREFIXES:
            for item in iter_objects(prefix=prefix):
                uploaded_at = item.uploaded_at
                if uploaded_at.tzinfo is None:
                    uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
                if uploaded_at < cutoff:
                    expired.append(item.url)
        for start in range(0, len(expired), 500):
            delete(expired[start:start + 500])
        return len(expired)

    def cleanup_all(self) -> dict:
        results = {}
        for key, task in (
            ("jobs_removed", self.cleanup_expired_jobs),
            ("downloads_removed", self.cleanup_expired_downloads),
            ("outputs_removed", self.cleanup_expired_outputs),
            ("blobs_removed", self.cleanup_expired_blobs),
        ):
            try:
                results[key] = task()
            except Exception:
                logger.exception("Cleanup step %s failed", key)
                results[key] = 0
        return results

    def claim_sweep(self) -> bool:
        """Return True (at most once per interval) if a sweep should run."""
        now = time.monotonic()
        with self._lock:
            if self._running or now - self._last_sweep < SWEEP_INTERVAL_SECONDS:
                return False
            self._running = True
            self._last_sweep = now
            return True

    def run_claimed_sweep(self) -> dict:
        try:
            return self.cleanup_all()
        finally:
            with self._lock:
                self._running = False


job_cleanup_service = JobCleanupService()
