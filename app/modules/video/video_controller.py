"""Controller for video downloader API operations."""

import logging
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from fastapi import HTTPException, Request

from app.core.exceptions import ProcessingError
from app.infrastructure.storage import storage
from app.modules.video.video_schema import VideoDownloadRequest, VideoInfoRequest
from app.modules.video.video_service import video_downloader_service
from app.shared.utils.download_util import download_response
from app.shared.utils.file_util import resolve_safe_path, unique_filename

logger = logging.getLogger(__name__)

_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}


def _persist_download(file_path: Path) -> Path:
    """Move a finished download from temp into shared output storage.

    Files left in the temp dir were only reachable from the instance
    that downloaded them and were never cleaned up.
    """
    output_path = resolve_safe_path(
        storage.processed_path,
        unique_filename(file_path.name),
    )
    try:
        storage.save(file_path, output_path)
    finally:
        file_path.unlink(missing_ok=True)
    return output_path


class VideoDownloaderController:
    """Handles HTTP API routing logic for video downloader operations."""

    def get_info(self, request: VideoInfoRequest) -> Dict[str, Any]:
        """Retrieve video details without downloading."""
        if not request.url or not request.url.strip():
            raise HTTPException(status_code=400, detail="Video URL must not be empty.")

        try:
            info = video_downloader_service.get_video_info(request.url.strip())
            return {
                "success": True,
                "data": info,
            }
        except ProcessingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("Controller error in get_info: %s", str(exc))
            raise HTTPException(status_code=500, detail="Failed to retrieve video information.")

    def download(self, request: Request, body: VideoDownloadRequest) -> Dict[str, Any]:
        """Download video/audio to server and return download metadata."""
        if not body.url or not body.url.strip():
            raise HTTPException(status_code=400, detail="Video URL must not be empty.")

        try:
            file_path = video_downloader_service.download_video(
                url=body.url.strip(),
                format_choice=body.format,
                quality_choice=body.quality,
            )

            output_path = _persist_download(file_path)
            filename = output_path.name

            return {
                "success": True,
                "filename": filename,
                "size_bytes": output_path.stat().st_size,
                # Relative, like every other tool: an absolute URL built
                # from the request uses http:// behind Vercel's TLS proxy,
                # which browsers block as mixed content.
                "download_url": (
                    f"/api/v1/tools/video/download/{quote(filename, safe='')}"
                ),
            }
        except ProcessingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("Controller error in download: %s", str(exc))
            raise HTTPException(status_code=500, detail="Failed to process video download.")

    def serve_file(self, filename: str):
        """Serve downloaded video or audio file for client download."""
        file_path = storage.materialize(
            resolve_safe_path(storage.processed_path, filename)
        )

        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found or expired.")

        return download_response(
            file_path,
            _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream"),
        )


video_downloader_controller = VideoDownloaderController()
