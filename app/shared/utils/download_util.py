"""Build download responses that also work on Vercel.

Vercel Functions cap response bodies at 4.5 MB, so streaming a larger
output (a PNG conversion, a PDF rendered to images, a downloaded video)
through the function fails there. When the file lives in Vercel Blob,
large downloads are redirected to the Blob URL instead.
"""

from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings
from app.infrastructure.storage import storage

# Stay safely below Vercel's 4.5 MB response-body limit.
VERCEL_RESPONSE_LIMIT_BYTES = 4 * 1024 * 1024


def _blob_download_url(file_path: Path, blob_key: str | None = None) -> str:
    try:
        if blob_key:
            from vercel.blob import get_download_url, head

            url = head(blob_key).url
            if settings.blob_access_mode == "private":
                url = get_download_url(url)
        else:
            url = storage.get_url(file_path)
    except Exception:
        return ""
    if url and settings.blob_access_mode == "public" and "download=" not in url:
        # Ask Blob to send Content-Disposition: attachment, since the
        # <a download> attribute is ignored for cross-origin links.
        url += ("&" if "?" in url else "?") + "download=1"
    return url


def download_response(
    file_path: Path,
    media_type: str,
    filename: str | None = None,
    blob_key: str | None = None,
):
    """Stream ``file_path``, or redirect to Blob when it is too large.

    ``blob_key`` names the Blob object when the file does not live under
    the storage adapter's own paths (e.g. job downloads).
    """
    if (
        settings.storage_driver == "vercel"
        and file_path.stat().st_size > VERCEL_RESPONSE_LIMIT_BYTES
    ):
        url = _blob_download_url(file_path, blob_key)
        if url:
            return RedirectResponse(url, status_code=307)
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename or file_path.name,
    )
