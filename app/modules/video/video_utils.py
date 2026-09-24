"""Helpers for the video downloader tool (yt-dlp access, formatting)."""

import ipaddress
import shutil
import socket
from typing import Any, Dict
from urllib.parse import urlsplit

from app.core.exceptions import ProcessingError

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}


def validate_public_url(url: str) -> str:
    """Reject URLs that would make the server fetch internal resources.

    yt-dlp's generic extractor downloads whatever a URL points to, so
    without this check ``file://``, ``http://127.0.0.1:...`` or cloud
    metadata endpoints (169.254.169.254) could be fetched and handed back
    to the requester. Only http(s) URLs whose host resolves exclusively
    to public addresses are allowed. (Redirects performed by yt-dlp are
    not re-checked; this blocks the direct cases.)
    """
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError as error:
        raise ProcessingError("Enter a valid http(s) video link.") from error
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ProcessingError("Enter a valid http(s) video link.")
    host = parts.hostname.strip("[]").lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise ProcessingError("Links to local or private addresses are not allowed.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [literal]
    else:
        try:
            infos = socket.getaddrinfo(host, parts.port or None, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError, OSError):
            # Unresolvable here means yt-dlp cannot reach it either; let
            # it produce its own "could not resolve" error.
            return url
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0].split("%", 1)[0]))
            except ValueError:
                continue
    for address in addresses:
        mapped = getattr(address, "ipv4_mapped", None) or address
        if not mapped.is_global or mapped.is_multicast:
            raise ProcessingError("Links to local or private addresses are not allowed.")
    return url


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
        # Without a postprocessor "mp3" silently produced .webm/.m4a
        # audio. Convert when ffmpeg is available; otherwise prefer a
        # native file of the requested type.
        if ffmpeg:
            return {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": format_choice,
                        "preferredquality": "192",
                    }
                ],
            }
        return {
            "format": (
                f"bestaudio[ext={format_choice}]/bestaudio[ext=m4a]"
                "/bestaudio/best"
            )
        }

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
