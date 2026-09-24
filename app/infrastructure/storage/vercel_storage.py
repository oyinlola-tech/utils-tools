"""Vercel Blob storage adapter.

Uses the official ``vercel`` Python SDK (``vercel.blob``) instead of a
hand-rolled REST client. The SDK handles the current API version headers,
retries with backoff for transient failures, content-type inference and
signed download URLs — all details the previous implementation got wrong,
which surfaced as failing tools on Vercel.

Blob keys mirror the local filesystem layout (``uploads/...``,
``processed/...``, ...) so the two drivers stay interchangeable. A local
mirror under the ephemeral temp dir keeps ``materialize()`` cheap for
short-lived serverless instances.
"""

import logging
import tempfile
from pathlib import Path

from vercel.blob import (
    BlobNotFoundError,
    delete,
    get,
    get_download_url,
    head,
    put,
)

from app.core.config import settings
from app.infrastructure.storage.base import StorageInterface

logger = logging.getLogger(__name__)

_LOCAL_ROOT = Path(tempfile.gettempdir()) / "vercel_storage"
# URL cache entries kept per instance (it previously grew forever).
_MAX_CACHED_URLS = 1000


class VercelStorage(StorageInterface):
    def __init__(self) -> None:
        self._access = settings.blob_access_mode
        # Blob path -> public URL returned by the SDK on upload, so
        # get_url() does not need a network round-trip for fresh files.
        self._urls: dict[str, str] = {}
        self.upload_path = _LOCAL_ROOT / "uploads"
        self.processed_path = _LOCAL_ROOT / "processed"
        self.compressed_path = _LOCAL_ROOT / "compressed"
        self.temp_path = _LOCAL_ROOT / "temp"

    def _check_token(self) -> None:
        if not settings.blob_read_write_token:
            raise RuntimeError(
                "BLOB_READ_WRITE_TOKEN is required for Vercel storage."
            )
        for directory in (
            self.upload_path,
            self.processed_path,
            self.compressed_path,
            self.temp_path,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _remember_url(self, blob_path: str, url: str) -> None:
        if len(self._urls) >= _MAX_CACHED_URLS:
            self._urls.pop(next(iter(self._urls)))
        self._urls[blob_path] = url

    def _blob_key(self, file_path: Path) -> str:
        try:
            return file_path.relative_to(_LOCAL_ROOT).as_posix()
        except ValueError:
            return file_path.as_posix()

    def write(self, file_path: Path, data: bytes) -> None:
        self._check_token()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        blob_path = self._blob_key(file_path)
        result = put(
            blob_path,
            data,
            access=self._access,
            overwrite=True,
        )
        self._remember_url(blob_path, result.url)

    def save(
        self,
        source_path: Path,
        destination_path: Path,
    ) -> Path:
        data = source_path.read_bytes()
        self.write(destination_path, data)
        return destination_path

    def read(self, file_path: Path) -> bytes:
        self._check_token()
        blob_path = self._blob_key(file_path)
        result = get(blob_path, access=self._access, use_cache=False)
        return result.content

    def materialize(self, file_path: Path) -> Path:
        if file_path.exists():
            return file_path
        try:
            result = get(
                self._blob_key(file_path),
                access=self._access,
                use_cache=False,
            )
        except BlobNotFoundError:
            return file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(result.content)
        return file_path

    def delete(self, file_path: Path) -> None:
        self._check_token()
        blob_path = self._blob_key(file_path)
        try:
            delete(blob_path)
        except BlobNotFoundError:
            pass
        self._urls.pop(blob_path, None)
        file_path.unlink(missing_ok=True)

    def exists(self, file_path: Path) -> bool:
        self._check_token()
        try:
            head(self._blob_key(file_path))
            return True
        except BlobNotFoundError:
            return False

    def get_size(self, file_path: Path) -> int:
        self._check_token()
        result = head(self._blob_key(file_path))
        return result.size

    def get_url(self, file_path: Path) -> str:
        self._check_token()
        blob_path = self._blob_key(file_path)
        url = self._urls.get(blob_path)
        if url is None:
            try:
                url = head(blob_path).url
            except BlobNotFoundError:
                return ""
            self._remember_url(blob_path, url)
        if self._access == "private":
            return get_download_url(url)
        return url


vercel_storage = VercelStorage()
