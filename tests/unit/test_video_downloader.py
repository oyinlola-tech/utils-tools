"""Unit tests for Video Downloader schema, service, controller, and routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ProcessingError
from app.main import app
from app.modules.video.video_schema import VideoDownloadRequest, VideoInfoRequest
from app.modules.video.video_service import video_downloader_service

client = TestClient(app)


def test_video_info_schema_validation():
    """Test VideoInfoRequest payload validation."""
    req = VideoInfoRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert req.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_video_download_schema_validation():
    """Test VideoDownloadRequest defaults and choices."""
    req = VideoDownloadRequest(url="https://tiktok.com/@user/video/12345")
    assert req.format == "mp4"
    assert req.quality == "best"

    req_audio = VideoDownloadRequest(
        url="https://youtube.com/watch?v=abc", format="mp3", quality="audio"
    )
    assert req_audio.format == "mp3"
    assert req_audio.quality == "audio"


@patch("yt_dlp.YoutubeDL")
def test_video_service_get_info_success(mock_ytdl):
    """Test get_video_info service method returning formatted dict."""
    mock_instance = MagicMock()
    mock_ytdl.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {
        "title": "Sample Video",
        "uploader": "Test Channel",
        "duration": 125,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor_key": "Youtube",
        "formats": [{"height": 1080}, {"height": 720}, {"height": 480}],
    }

    result = video_downloader_service.get_video_info("https://youtube.com/watch?v=test")

    assert result["title"] == "Sample Video"
    assert result["uploader"] == "Test Channel"
    assert result["duration_seconds"] == 125
    assert result["duration_formatted"] == "02:05"
    assert result["platform"] == "Youtube"
    assert "1080p" in result["available_qualities"]


@patch("yt_dlp.YoutubeDL")
def test_video_service_get_info_error(mock_ytdl):
    """Test get_video_info handling yt-dlp error."""
    import yt_dlp

    mock_instance = MagicMock()
    mock_ytdl.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.side_effect = yt_dlp.utils.DownloadError("Invalid URL")

    with pytest.raises(ProcessingError) as exc_info:
        video_downloader_service.get_video_info("https://invalid-link.com")

    assert "Could not retrieve video details" in str(exc_info.value)


def test_api_video_info_endpoint():
    """Test POST /api/v1/tools/video/info API route."""
    with patch("app.modules.video.video_service.video_downloader_service.get_video_info") as mock_info:
        mock_info.return_value = {
            "url": "https://youtube.com/watch?v=123",
            "title": "Mock Video",
            "uploader": "Mock User",
            "duration_seconds": 60,
            "duration_formatted": "01:00",
            "thumbnail": "http://img.png",
            "platform": "Youtube",
            "available_qualities": ["720p"],
        }

        response = client.post(
            "/api/v1/tools/video/info",
            json={"url": "https://youtube.com/watch?v=123"},
        )

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["title"] == "Mock Video"


def test_api_video_download_endpoint():
    """POST /download persists the file and returns a relative URL."""
    from app.infrastructure.storage import storage

    storage.temp_path.mkdir(parents=True, exist_ok=True)
    source = storage.temp_path / "video_test_sample.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64)

    with patch(
        "app.modules.video.video_service.video_downloader_service.download_video"
    ) as mock_dl:
        mock_dl.return_value = source
        response = client.post(
            "/api/v1/tools/video/download",
            json={
                "url": "https://youtube.com/watch?v=123",
                "format": "mp4",
                "quality": "720p",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["filename"].startswith("video_test_sample_")
    assert data["filename"].endswith(".mp4")
    assert data["size_bytes"] == 76
    # Relative: absolute http:// URLs are blocked as mixed content on
    # HTTPS deployments behind a TLS-terminating proxy.
    assert data["download_url"] == (
        f"/api/v1/tools/video/download/{data['filename']}"
    )
    assert not source.exists()

    served = client.get(data["download_url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "video/mp4"
    assert len(served.content) == 76
    storage.delete(storage.processed_path / data["filename"])


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1:8000/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://localhost/video.mp4",
        "http://10.1.2.3/video.mp4",
        "ftp://example.com/video.mp4",
    ],
)
def test_video_endpoints_reject_internal_urls(url):
    with patch("yt_dlp.YoutubeDL") as mock_ytdl:
        info = client.post("/api/v1/tools/video/info", json={"url": url})
        download = client.post(
            "/api/v1/tools/video/download", json={"url": url}
        )
        mock_ytdl.assert_not_called()
    assert info.status_code == 400
    assert download.status_code == 400


def test_select_format_audio_extraction():
    from app.modules.video.video_utils import select_format

    with_ffmpeg = select_format("mp3", "audio", True)
    assert with_ffmpeg["postprocessors"][0]["preferredcodec"] == "mp3"
    without = select_format("mp3", "audio", False)
    assert "postprocessors" not in without
    assert without["format"].startswith("bestaudio[ext=mp3]")
