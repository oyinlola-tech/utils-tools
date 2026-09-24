"""FastAPI route definitions for Video Downloader tools."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.api import API_PREFIX
from app.modules.video.video_controller import video_downloader_controller
from app.modules.video.video_schema import VideoDownloadRequest, VideoInfoRequest
from app.shared.utils.file_util import is_safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{API_PREFIX}/tools/video",
    tags=["Video Tools"],
)


@router.post("/info")
def get_video_info(request: VideoInfoRequest):
    """Fetch video metadata, title, duration, thumbnail, and format options."""
    logger.info("get_video_info for URL: %s", request.url)
    return video_downloader_controller.get_info(request)


@router.post("/download")
def download_video(request: Request, body: VideoDownloadRequest):
    """Download video/audio file and return download link."""
    logger.info("download_video: url=%s, format=%s, quality=%s", body.url, body.format, body.quality)
    return video_downloader_controller.download(request, body)


@router.get("/download/{filename}")
def download_video_file(filename: str):
    """Serve the downloaded video/audio file."""
    if not is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return video_downloader_controller.serve_file(filename)
