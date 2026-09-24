"""Validation schemas for Video Downloader API endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class VideoInfoRequest(BaseModel):
    """Payload for fetching video metadata."""

    url: str = Field(..., description="Target video URL (YouTube, TikTok, Facebook, Instagram, Twitter, etc.)")


class VideoDownloadRequest(BaseModel):
    """Payload for initiating a video download."""

    url: str = Field(..., description="Target video URL")
    format: Literal["mp4", "mp3", "webm", "m4a"] = Field(
        default="mp4", description="Output format (mp4 for video, mp3 for audio)"
    )
    # Must accept every height /info can report (e.g. "240p", "1440p").
    quality: str = Field(
        default="best",
        pattern=r"^(best|audio|\d{3,4}p)$",
        description="Resolution or quality preference",
    )
