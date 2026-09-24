"""Helpers for the video downloader tool (yt-dlp access, formatting)."""

import shutil
from typing import Any, Dict


def _get_yt_dlp():
    """Import yt-dlp lazily so the app boots when it is not installed."""
    import yt_dlp

    return yt_dlp


def ffmpeg_available() -> bool:
    """Whether ffmpeg is on PATH (required to merge separate streams)."""
    return shutil.which("ffmpeg") is not None


def select_format(
    format_choice: str,
    quality_choice: str,
    ffmpeg: bool,
) -> Dict[str, Any]:
    """Build the yt-dlp format selector for the requested output.

    Prefers pre-muxed single-file formats when ffmpeg is missing so
    downloads do not fail on merge; falls back to video+audio merge
    when ffmpeg is present.
    """
    if format_choice in ("mp3", "m4a"):
        return {"format": "bestaudio/best"}

    height = quality_choice[:-1] if quality_choice.endswith("p") else ""
    if height.isdigit():
        if ffmpeg:
            selector = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
        else:
            selector = f"best[height<={height}]/bestvideo[height<={height}]+bestaudio/best"
    else:
        selector = "best/bestvideo+bestaudio"

    options: Dict[str, Any] = {"format": selector}
    if format_choice in ("mp4", "webm"):
        options["merge_output_format"] = format_choice
    return options


def format_duration(seconds: int) -> str:
    """Format seconds into MM:SS or HH:MM:SS string."""
    if not seconds:
        return "00:00"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
