"""Service handling video metadata extraction and video downloads using yt-dlp."""

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.core.exceptions import ProcessingError
from app.core.logging import get_tool_logger
from app.modules.video.video_utils import (
    _get_yt_dlp,
    ffmpeg_available,
    format_duration,
    select_format,
)

logger = logging.getLogger(__name__)


class VideoDownloaderService:
    """Business logic for querying and downloading online videos."""

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Fetch video metadata and available qualities without downloading."""
        tool_logger = get_tool_logger("video-downloader")
        started = time.monotonic()
        yt_dlp = _get_yt_dlp()
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ProcessingError(
                        "Unable to extract video information from the provided URL."
                    )
                if info.get("entries"):
                    info = info["entries"][0]

                title = info.get("title", "Untitled Video")
                uploader = (
                    info.get("uploader")
                    or info.get("channel")
                    or info.get("creator")
                    or "Unknown"
                )
                duration = info.get("duration") or 0
                thumbnail = info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", "")
                extractor = info.get("extractor_key") or info.get("extractor") or "Unknown"

                available_qualities = self._collect_qualities(info)
                tool_logger.info(
                    "info fetched for %s: '%s' (%s, %d qualities) in %.2fs",
                    url, title, extractor, len(available_qualities),
                    time.monotonic() - started,
                )
                return {
                    "url": url,
                    "title": title,
                    "uploader": uploader,
                    "duration_seconds": duration,
                    "duration_formatted": format_duration(duration),
                    "thumbnail": thumbnail,
                    "platform": extractor,
                    "available_qualities": available_qualities,
                }
        except yt_dlp.utils.DownloadError as exc:
            tool_logger.warning("yt-dlp extraction error for URL %s: %s", url, str(exc))
            raise ProcessingError(f"Could not retrieve video details: {exc!s}")
        except Exception as exc:
            tool_logger.error("Unexpected error fetching video info for URL %s: %s", url, str(exc))
            raise ProcessingError(f"An error occurred while fetching video info: {exc!s}")

    def download_video(
        self,
        url: str,
        format_choice: str = "mp4",
        quality_choice: str = "best",
    ) -> Path:
        """Download video/audio to local storage and return the output file path."""
        tool_logger = get_tool_logger("video-downloader")
        started = time.monotonic()
        yt_dlp = _get_yt_dlp()
        download_dir = Path(settings.temp_directory)
        download_dir.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4().hex[:8]
        output_template = download_dir / f"video_{job_id}_%(title)s.%(ext)s"

        base_opts = {
            "outtmpl": str(output_template),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        base_opts.update(select_format(format_choice, quality_choice, ffmpeg_available()))

        selected_formats = [base_opts["format"], "best"]
        for selected in selected_formats:
            ydl_opts = {**base_opts, "format": selected}
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        raise ProcessingError("Failed to download video.")
                    downloaded_path = self._resolve_downloaded_path(
                        download_dir, job_id, ydl, info
                    )
                    tool_logger.info(
                        "downloaded '%s' (%d bytes, %s) in %.2fs",
                        url, downloaded_path.stat().st_size, downloaded_path.name,
                        time.monotonic() - started,
                    )
                    return downloaded_path
            except yt_dlp.utils.DownloadError as exc:
                if selected == "best":
                    tool_logger.warning("yt-dlp download error for URL %s: %s", url, str(exc))
                    raise ProcessingError(f"Video download failed: {exc!s}")
                tool_logger.info(
                    "format '%s' failed (%s); retrying with best", selected, exc
                )
            except Exception as exc:
                tool_logger.error("Unexpected error downloading video for URL %s: %s", url, str(exc))
                raise ProcessingError(f"An error occurred while downloading the video: {exc!s}")
        raise ProcessingError("Failed to download video.")

    @staticmethod
    def _collect_qualities(info: Dict[str, Any]) -> list[str]:
        heights = {
            fmt.get("height")
            for fmt in info.get("formats", [])
            if fmt.get("height") and isinstance(fmt.get("height"), int) and fmt["height"] >= 144
        }
        if not heights:
            return ["720p", "480p", "360p"]
        return [f"{h}p" for h in sorted(heights, reverse=True)]

    @staticmethod
    def _resolve_downloaded_path(
        download_dir: Path,
        job_id: str,
        ydl: Any,
        info: Dict[str, Any],
    ) -> Path:
        downloaded_path = Path(ydl.prepare_filename(info))
        if downloaded_path.exists():
            return downloaded_path
        matches = list(download_dir.glob(f"video_{job_id}_*"))
        if matches:
            return matches[0]
        raise ProcessingError("Downloaded file not found after processing.")


video_downloader_service = VideoDownloaderService()
