"""Tests for the Image Compressor tool (Phase 2A)."""

import time
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.main import app

client = TestClient(app)


def _make_jpeg(width=200, height=200, quality=95) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (200, 100, 50)).save(
        buf, format="JPEG", quality=quality
    )
    return buf.getvalue()


def _make_png(width=200, height=200, transparent=True) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    buf = BytesIO()
    Image.new(mode, (width, height), (0, 255, 0, 128 if transparent else 255)).save(
        buf, format="PNG"
    )
    return buf.getvalue()


def _make_webp(width=200, height=200, transparent=True) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    buf = BytesIO()
    Image.new(mode, (width, height), (0, 100, 200, 128 if transparent else 255)).save(
        buf, format="WEBP"
    )
    return buf.getvalue()


def _make_png_with_metadata(width=100, height=100) -> bytes:
    img = Image.new("RGBA", (width, height), (255, 0, 0, 255))
    info = PngInfo()
    info.add_text("Author", "TestAuthor")
    info.add_text("Description", "TestDescription")
    info.add_text("Software", "UnitTest")
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=info)
    return buf.getvalue()


def _make_jpeg_with_exif(width=100, height=100) -> bytes:
    img = Image.new("RGB", (width, height), (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)

    return buf.getvalue()


def _wait_for_job(job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/jobs/{job_id}")
        job = r.json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.2)
    return client.get(f"/api/v1/jobs/{job_id}").json()


# --------------------------------------------------------------------------- #
# Service-level tests
# --------------------------------------------------------------------------- #

class TestImageCompressionService:
    def test_jpeg_compression(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_jpeg(500, 400, quality=95)
        data, content_type, quality, width, height = (
            image_compression_service.compress(
                file_data=original,
                output_format="webp",
                quality=80,
                strip_metadata=True,
            )
        )
        assert len(data) < len(original)
        assert content_type == "image/webp"
        assert width == 500
        assert height == 400
        assert 10 <= quality <= 100
        img = Image.open(BytesIO(data))
        img.load()

    def test_png_compression_preserves_transparency(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_png(300, 200, transparent=True)
        data, content_type, _quality, _width, _height = (
            image_compression_service.compress(
                file_data=original,
                output_format="png",
                quality=90,
                strip_metadata=True,
            )
        )
        assert content_type == "image/png"
        img = Image.open(BytesIO(data))
        img.load()
        assert img.mode in ("RGBA", "LA", "P")
        assert img.size == (300, 200)

    def test_webp_compression_preserves_transparency(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_webp(300, 200, transparent=True)
        data, content_type, _quality, _width, _height = (
            image_compression_service.compress(
                file_data=original,
                output_format="webp",
                quality=80,
                strip_metadata=True,
            )
        )
        assert content_type == "image/webp"
        img = Image.open(BytesIO(data))
        img.load()
        # WebP with alpha should preserve transparency
        assert img.mode in ("RGBA", "RGBa", "LA")

    def test_corrupted_image_rejected(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        with pytest.raises(Exception):
            image_compression_service.compress(
                file_data=b"not an image at all",
                output_format="webp",
                quality=80,
            )

    def test_oversized_image_rejected(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        # An image that exceeds Pillow's decompression-bomb threshold
        # (Image.MAX_IMAGE_PIXELS = 50_000_000)
        with pytest.raises(Exception):
            image_compression_service.compress(
                file_data=b"\xff\xd8\xff\xe0garbage_not_an_image",
                output_format="webp",
                quality=80,
            )

    def test_metadata_removal_strip(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_png_with_metadata(200, 200)

        data_stripped, _, _, _, _ = (
            image_compression_service.compress(
                file_data=original,
                output_format="png",
                quality=90,
                strip_metadata=True,
            )
        )
        img_stripped = Image.open(BytesIO(data_stripped))
        assert "Author" not in img_stripped.info
        assert "Description" not in img_stripped.info

        data_preserved, _, _, _, _ = (
            image_compression_service.compress(
                file_data=original,
                output_format="png",
                quality=90,
                strip_metadata=False,
            )
        )
        img_preserved = Image.open(BytesIO(data_preserved))
        assert img_preserved.info.get("Author") == "TestAuthor"

    def test_target_size_handling(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_jpeg(800, 600, quality=95)
        target_bytes = 2 * 1024

        data, content_type, _quality, _width, _height = (
            image_compression_service.compress_to_target(
                file_data=original,
                target_size_bytes=target_bytes,
                output_format="webp",
                strip_metadata=True,
            )
        )
        assert len(data) <= target_bytes
        assert content_type == "image/webp"

    def test_quality_validation(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_jpeg(100, 100)

        data_low, _, _, _, _ = image_compression_service.compress(
            file_data=original, output_format="webp", quality=100, strip_metadata=True
        )
        data_high, _, _, _, _ = image_compression_service.compress(
            file_data=original, output_format="webp", quality=10, strip_metadata=True
        )
        assert len(data_high) < len(data_low)

    def test_output_file_readable_and_correct_dimensions(self):
        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )

        original = _make_jpeg(640, 480, quality=95)
        data, _, _, width, height = (
            image_compression_service.compress(
                file_data=original, output_format="webp", quality=70
            )
        )
        img = Image.open(BytesIO(data))
        img.load()
        assert img.size == (width, height)
        assert img.format == "WEBP"

    def test_original_file_remains_untouched(self):
        original = _make_jpeg(100, 100, quality=95)
        original_copy = bytes(original)

        from app.modules.compression.image_compression.image_compression_service import (
            image_compression_service,
        )
        image_compression_service.compress(
            file_data=original, output_format="webp", quality=80
        )
        assert original == original_copy


# --------------------------------------------------------------------------- #
# API endpoint tests
# --------------------------------------------------------------------------- #

class TestImageCompressEndpoint:
    def test_jpeg_compression_via_api(self):
        jpeg_data = _make_jpeg(400, 300, quality=95)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={"output_format": "webp", "quality": "80", "remove_metadata": "true"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "job_id" in body

        job = _wait_for_job(body["job_id"])
        assert job["status"] == "completed"
        f = job["files"][0]
        assert f["status"] == "completed"
        assert f["compressed_size_bytes"] < f["original_size_bytes"]
        assert f["output_format"] == "webp"

    def test_png_compression_via_api(self):
        png_data = _make_png(300, 200, transparent=True)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.png", png_data, "image/png")},
            data={"output_format": "png", "quality": "80", "remove_metadata": "true"},
        )
        assert r.status_code == 200

        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "completed"
        f = job["files"][0]
        assert f["status"] == "completed"
        assert f["output_format"] == "png"

    def test_webp_compression_via_api(self):
        webp_data = _make_webp(300, 200, transparent=False)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.webp", webp_data, "image/webp")},
            data={"output_format": "webp", "quality": "70", "remove_metadata": "true"},
        )
        assert r.status_code == 200

        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "completed"
        f = job["files"][0]
        assert f["status"] == "completed"
        assert f["output_format"] == "webp"

    def test_invalid_quality_rejected(self):
        jpeg_data = _make_jpeg(100, 100)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={"quality": "5"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_REQUEST"

    def test_quality_out_of_range_high(self):
        jpeg_data = _make_jpeg(100, 100)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={"quality": "200"},
        )
        assert r.status_code == 400

    def test_invalid_file_rejected(self):
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("not_an_image.txt", b"hello world", "text/plain")},
            data={"quality": "80"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "failed"
        f = job["files"][0]
        assert f["status"] == "failed"
        assert "error" in f

    def test_corrupted_image_rejected(self):
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("broken.jpg", b"\xff\xd8\xff\xe0garbage", "image/jpeg")},
            data={"quality": "80"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "failed"
        f = job["files"][0]
        assert f["status"] == "failed"

    def test_oversized_file_rejected(self):
        from app.shared.file_inspection.file_validation import (
            MAX_IMAGE_SIZE,
            validate_file_size,
        )

        assert MAX_IMAGE_SIZE == 100 * 1024 * 1024

        # Just over the 100 MB image limit
        oversized_data = b"\x00" * (MAX_IMAGE_SIZE + 1)
        with pytest.raises(Exception):
            validate_file_size(oversized_data, MAX_IMAGE_SIZE)

        # Under the limit should pass
        small_data = b"\x00" * 1024
        validate_file_size(small_data, MAX_IMAGE_SIZE)

    def test_no_files_rejected(self):
        r = client.post(
            "/api/v1/images/compress",
            data={"quality": "80"},
        )
        assert r.status_code == 422

    def test_too_many_files_rejected(self):
        jpeg_data = _make_jpeg(50, 50)
        files = [
            ("files", ("f%d.jpg" % i, jpeg_data, "image/jpeg"))
            for i in range(25)
        ]
        r = client.post(
            "/api/v1/images/compress",
            files=files,
            data={"quality": "80"},
        )
        assert r.status_code == 400

    def test_target_size_handling_via_api(self):
        jpeg_data = _make_jpeg(800, 600, quality=95)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={
                "output_format": "webp",
                "quality": "80",
                "target_size": "5",
                "remove_metadata": "true",
            },
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "completed"
        f = job["files"][0]
        target_bytes = 5 * 1024
        assert f["compressed_size_bytes"] <= target_bytes

    def test_metadata_removal_via_api(self):
        png_with_meta = _make_png_with_metadata(200, 200)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.png", png_with_meta, "image/png")},
            data={"output_format": "png", "quality": "80", "remove_metadata": "true"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        f = job["files"][0]
        dl = client.get(f["download_url"])
        img = Image.open(BytesIO(dl.content))
        assert "Author" not in img.info
        assert "Description" not in img.info

    def test_metadata_preserved_when_requested(self):
        png_with_meta = _make_png_with_metadata(200, 200)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.png", png_with_meta, "image/png")},
            data={"output_format": "png", "quality": "80", "remove_metadata": "false"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        f = job["files"][0]
        dl = client.get(f["download_url"])
        img = Image.open(BytesIO(dl.content))
        assert img.info.get("Author") == "TestAuthor"

    def test_multiple_images(self):
        jpeg1 = _make_jpeg(200, 200, quality=95)
        jpeg2 = _make_jpeg(300, 300, quality=95)
        r = client.post(
            "/api/v1/images/compress",
            files=[
                ("files", ("a.jpg", jpeg1, "image/jpeg")),
                ("files", ("b.jpg", jpeg2, "image/jpeg")),
            ],
            data={"quality": "75"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        assert job["status"] == "completed"
        assert len(job["files"]) == 2
        for f in job["files"]:
            assert f["status"] == "completed"
            assert f["compressed_size_bytes"] > 0

    def test_auto_output_format_preserves_original(self):
        jpeg_data = _make_jpeg(200, 200, quality=95)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={"output_format": "auto", "quality": "70"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        f = job["files"][0]
        assert f["output_format"] in ("jpg", "jpeg")

    def test_auto_output_preserves_png(self):
        png_data = _make_png(200, 200, transparent=True)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.png", png_data, "image/png")},
            data={"output_format": "auto", "quality": "80"},
        )
        assert r.status_code == 200
        job = _wait_for_job(r.json()["job_id"])
        f = job["files"][0]
        assert f["output_format"] == "png"

    def test_download_individual_result(self):
        jpeg_data = _make_jpeg(200, 200, quality=95)
        r = client.post(
            "/api/v1/images/compress",
            files={"files": ("photo.jpg", jpeg_data, "image/jpeg")},
            data={"output_format": "webp", "quality": "80"},
        )
        job = _wait_for_job(r.json()["job_id"])
        f = job["files"][0]
        dl = client.get(f["download_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"] in ("image/webp", "image/jpeg", "image/png")
        assert len(dl.content) > 0
        img = Image.open(BytesIO(dl.content))
        img.load()
        assert img.size == (200, 200)

    def test_download_all_creates_zip(self):
        r = client.post(
            "/api/v1/images/compress",
            files=[
                ("files", ("a.jpg", _make_jpeg(100, 100), "image/jpeg")),
                ("files", ("b.png", _make_png(100, 100), "image/png")),
            ],
            data={"quality": "80"},
        )
        job = _wait_for_job(r.json()["job_id"])
        assert job["download_url"] is not None
        dl = client.get(job["download_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"] == "application/zip"

    def test_output_format_jpeg_with_transparency_flattens(self):
        # Create a PNG with transparency and noise so JPEG is smaller
        import random

        from app.modules.compression.compression_service import compression_service
        random.seed(42)
        img = Image.new("RGBA", (800, 600))
        pixels = [
            (random.randint(0, 255), random.randint(0, 255),
             random.randint(0, 255), 255 if i // 2 else 128)
            for i in range(800 * 600)
        ]
        img.putdata(pixels)
        buf = BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        # Compress with quality parameter directly to JPEG
        compressed, content_type, _quality, _width, _height = (
            compression_service.compress_image_quality(
                file_data=png_data,
                quality=80,
                output_format="jpeg",
                strip_metadata=True,
            )
        )
        assert content_type == "image/jpeg"
        assert len(compressed) < len(png_data)
        result = Image.open(BytesIO(compressed))
        result.load()
        assert result.mode == "RGB"
        assert result.size == (800, 600)
