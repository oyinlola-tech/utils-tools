"""Build download responses that also work on Vercel.

Vercel Functions cap response bodies at 4.5 MB, so streaming a larger
output (a PNG conversion, a PDF rendered to images, a downloaded video)
through the function fails there. When the file lives in Vercel Blob,
large downloads are redirected to the Blob URL instead.
"""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings
from app.infrastructure.storage import storage

# Stay safely below Vercel's 4.5 MB response-body limit.
VERCEL_RESPONSE_LIMIT_BYTES = 4 * 1024 * 1024


def _blob_download_url(file_path: Path, blob_key: str | None = None) -> str:
    """A browser-openable Blob URL, or "" when there isn't one.

    Private stores have none: their URLs need the server's token, so a
    redirect would hand the browser a link it can't open.
    """
    from app.infrastructure.storage.blob_access import access_mode

    if access_mode() != "public":
        return ""
    try:
        if blob_key:
            from vercel.blob import head

            url = head(blob_key).url
        else:
            url = storage.get_url(file_path)
    except Exception:
        return ""
    if url and "download=" not in url:
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
        # Streaming it would exceed Vercel's 4.5 MB response cap and fail
        # with an opaque platform error; say what happened instead.
        raise HTTPException(
            status_code=413,
            detail=(
                "This result is larger than the hosting platform can deliver "
                "(4.5 MB). Try a smaller file or a more compact output format."
            ),
        )
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename or file_path.name,
    )
