"""Comprehensive tests for the Image Resizer feature."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.modules.image.image_service import image_service

client = TestClient(app)


def _png_bytes(size=(120, 80), color=(255, 0, 0, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpg_bytes(size=(120, 80)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (10, 200, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _webp_bytes(size=(120, 80)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, (0, 100, 255, 200)).save(buffer, format="WEBP")
    return buffer.getvalue()


def _animated_gif_bytes() -> bytes:
    buffer = BytesIO()
    frames = [
        Image.new("RGB", (50, 50), (i * 80, 0, 0))
        for i in range(3)
    ]
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=100,
    )
    return buffer.getvalue()


# ─── Service-level resize tests ──────────────────────────────


def test_resize_percent_preserves_aspect():
    result = image_service.resize(
        _png_bytes((400, 300)), resize_mode="percent", percent=50
    )
    assert result["width"] == 200
    assert result["height"] == 150
    assert result["extension"] == "png"


def test_resize_exact_dimensions():
    result = image_service.resize(
        _png_bytes((400, 300)),
        resize_mode="exact",
        width=200,
        height=100,
        maintain_aspect_ratio=False,
    )
    assert result["width"] == 200
    assert result["height"] == 100


def test_resize_aspect_width_updates_height():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="aspect",
        width=100,
    )
    assert result["width"] == 100
    assert result["height"] == 50


def test_resize_aspect_height_updates_width():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="aspect",
        height=50,
    )
    assert result["width"] == 100
    assert result["height"] == 50


def test_resize_max_dimension_downscales():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="max",
        max_dimension=200,
    )
    assert result["width"] == 200
    assert result["height"] == 100


def test_resize_max_dimension_does_not_upscale():
    result = image_service.resize(
        _png_bytes((50, 50)),
        resize_mode="max",
        max_dimension=500,
        allow_upscale=False,
    )
    assert result["width"] == 50
    assert result["height"] == 50


def test_resize_max_dimension_upscale_when_allowed():
    result = image_service.resize(
        _png_bytes((50, 50)),
        resize_mode="max",
        max_dimension=500,
        allow_upscale=True,
    )
    assert result["width"] == 500
    assert result["height"] == 500


def test_resize_auto_preserves_png():
    result = image_service.resize(
        _png_bytes(), resize_mode="aspect", width=50, output_format="auto"
    )
    assert result["extension"] == "png"
    assert result["input_format"] == "PNG"


def test_resize_auto_preserves_jpeg():
    result = image_service.resize(
        _jpg_bytes(), resize_mode="aspect", width=50, output_format="auto"
    )
    assert result["extension"] == "jpg"
    assert result["input_format"] == "JPEG"


def test_resize_jpeg_output_quality():
    result = image_service.resize(
        _jpg_bytes((200, 200)),
        resize_mode="aspect",
        width=100,
        output_format="jpg",
        quality=30,
    )
    assert result["extension"] == "jpg"
    assert result["width"] == 100
    assert result["height"] == 100


def test_resize_png_keeps_transparency():
    result = image_service.resize(
        _png_bytes(), resize_mode="aspect", width=50, output_format="png"
    )
    assert result["has_alpha"] is True
    assert result["flattened"] is False


def test_resize_png_to_jpeg_flattens_transparency():
    result = image_service.resize(
        _png_bytes(),
        resize_mode="aspect",
        width=50,
        output_format="jpg",
        background_color="#ffffff",
    )
    assert result["flattened"] is True
    assert result["extension"] == "jpg"


def test_resize_png_to_jpeg_custom_background():
    result = image_service.resize(
        _png_bytes(size=(10, 10), color=(0, 0, 255, 255)),
        resize_mode="exact",
        width=5,
        height=5,
        output_format="jpg",
        background_color="#000000",
    )
    assert result["flattened"] is True
    assert result["extension"] == "jpg"


def test_resize_webp_keeps_transparency():
    result = image_service.resize(
        _webp_bytes(), resize_mode="aspect", width=50, output_format="webp"
    )
    assert result["has_alpha"] is True


def test_resize_rejects_animated_gif():
    with pytest.raises(ValueError, match="Animated"):
        image_service.resize(
            _animated_gif_bytes(),
            resize_mode="aspect",
            width=25,
        )


def test_resize_rejects_negative_width():
    with pytest.raises(ValueError, match="positive"):
        image_service.resize(
            _png_bytes(),
            resize_mode="exact",
            width=-10,
            height=50,
        )


def test_resize_rejects_zero_height():
    with pytest.raises(ValueError, match="positive"):
        image_service.resize(
            _png_bytes(),
            resize_mode="exact",
            width=10,
            height=0,
        )


def test_resize_rejects_zero_percent():
    with pytest.raises(ValueError, match="greater than zero"):
        image_service.resize(
            _png_bytes(),
            resize_mode="percent",
            percent=0,
        )


def test_resize_rejects_negative_percent():
    with pytest.raises(ValueError, match="greater than zero"):
        image_service.resize(
            _png_bytes(),
            resize_mode="percent",
            percent=-10,
        )


def test_resize_rejects_invalid_mode():
    with pytest.raises(ValueError, match="Unknown resize mode"):
        image_service.resize(
            _png_bytes(),
            resize_mode="invalid",
            width=50,
        )


def test_resize_rejects_oversized_dimensions():
    with pytest.raises(ValueError, match="exceeds"):
        image_service.resize(
            _png_bytes(),
            resize_mode="exact",
            width=10000,
            height=10000,
        )


def test_resize_metadata_removed():
    result = image_service.resize(
        _jpg_bytes(),
        resize_mode="aspect",
        width=50,
        output_format="jpg",
        strip_metadata=True,
    )
    assert result["width"] == 50
    assert result["height"] == 33


def test_resize_corrupted_image():
    with pytest.raises((OSError, ValueError, RuntimeError)):
        image_service.resize(
            b"not an image data at all",
            resize_mode="aspect",
            width=50,
        )


# ─── Convert tests ───────────────────────────────────────────


def test_convert_png_to_jpeg():
    result = image_service.convert(_png_bytes(), "jpg")
    assert result["extension"] == "jpg"
    assert result["content_type"] == "image/jpeg"
    assert result["flattened"] is True


def test_convert_jpeg_to_webp():
    result = image_service.convert(_jpg_bytes(), "webp")
    assert result["extension"] == "webp"
    assert result["content_type"] == "image/webp"


def test_convert_png_to_webp_preserves_alpha():
    result = image_service.convert(_png_bytes(), "webp")
    assert result["extension"] == "webp"
    assert result["has_alpha"] is True


def test_convert_cmyk_jpeg_to_rgb():
    buffer = BytesIO()
    Image.new("CMYK", (100, 100), (100, 50, 25, 10)).save(buffer, format="JPEG")
    result = image_service.convert(buffer.getvalue(), "jpg")
    assert result["extension"] == "jpg"
    assert result["content_type"] == "image/jpeg"


def test_convert_rejects_animated_gif():
    with pytest.raises(ValueError, match="Animated"):
        image_service.convert(_animated_gif_bytes(), "png")


def test_convert_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unsupported"):
        image_service.convert(_png_bytes(), "tiff")


def test_convert_with_quality():
    result = image_service.convert(
        _jpg_bytes((200, 200)), "jpg", quality=30
    )
    assert result["extension"] == "jpg"


# ─── API-level tests ─────────────────────────────────────────


def test_api_resize_single_file():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "aspect", "width": "50"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["total_files"] == 1
    assert body["successful_files"] == 1
    assert body["failed_files"] == 0
    result = body["results"][0]
    assert result["width"] == 50
    assert result["height"] == 33
    assert result["original_width"] == 120
    assert result["original_height"] == 80


def test_api_resize_multiple_files():
    response = client.post(
        "/api/v1/images/resize",
        files=[
            ("files", ("a.png", _png_bytes(), "image/png")),
            ("files", ("b.jpg", _jpg_bytes(), "image/jpeg")),
        ],
        data={
            "resize_mode": "exact",
            "width": "50",
            "height": "50",
            "maintain_aspect_ratio": "false",
            "allow_upscale": "true",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_files"] == 2
    assert body["successful_files"] == 2
    assert body["failed_files"] == 0
    for result in body["results"]:
        assert result["width"] == 50
        assert result["height"] == 50


def test_api_resize_per_file_failure():
    response = client.post(
        "/api/v1/images/resize",
        files=[
            ("files", ("good.png", _png_bytes(), "image/png")),
            ("files", ("bad.png", b"not an image", "image/png")),
        ],
        data={"resize_mode": "aspect", "width": "50"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_files"] == 2
    assert body["successful_files"] == 1
    assert body["failed_files"] == 1
    assert len(body["failures"]) == 1
    assert body["failures"][0]["filename"] == "bad.png"


def test_api_resize_rejects_negative_dimension():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "exact", "width": "-10", "height": "50"},
    )
    assert response.status_code == 400


def test_api_resize_rejects_invalid_mode():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "invalid", "width": "50"},
    )
    assert response.status_code == 400


def test_api_resize_rejects_no_files():
    response = client.post(
        "/api/v1/images/resize",
        files=[],
        data={"resize_mode": "aspect", "width": "50"},
    )
    assert response.status_code in (400, 422)


def test_api_resize_rejects_too_many_files():
    files = [
        ("files", (f"img{i}.png", _png_bytes(), "image/png"))
        for i in range(51)
    ]
    response = client.post(
        "/api/v1/images/resize",
        files=files,
        data={"resize_mode": "aspect", "width": "50"},
    )
    assert response.status_code == 400
    assert "Too many" in response.json()["error"]["message"]


def test_api_resize_rejects_invalid_quality():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "aspect", "width": "50", "quality": "150"},
    )
    assert response.status_code == 400


def test_api_resize_rejects_invalid_output_format():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "aspect", "width": "50", "output_format": "gif"},
    )
    assert response.status_code == 400


def test_api_resize_download_url():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "aspect", "width": "50"},
    )
    result = response.json()["results"][0]
    assert result["download_url"].startswith("/api/v1/tools/image/download/")


def test_api_resize_transparency_to_jpeg():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("transparent.png", _png_bytes(), "image/png"))],
        data={
            "resize_mode": "aspect",
            "width": "50",
            "output_format": "jpg",
            "background_color": "#ffffff",
        },
    )
    result = response.json()["results"][0]
    assert result["output_format"] == "jpg"
    assert result["details"]["flattened"] is True


def test_api_resize_auto_format_preserves_source():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("photo.jpg", _jpg_bytes(), "image/jpeg"))],
        data={"resize_mode": "aspect", "width": "50", "output_format": "auto"},
    )
    result = response.json()["results"][0]
    assert result["output_format"] == "jpg"


def test_api_resize_rejects_oversized_dimensions():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "exact", "width": "99999", "height": "99999"},
    )
    assert response.status_code == 400
    assert "exceeds" in response.json()["error"]["message"].lower()


def test_api_resize_original_file_unchanged():
    original = _png_bytes()
    client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", original, "image/png"))],
        data={"resize_mode": "aspect", "width": "50"},
    )
    assert original == _png_bytes()


def test_api_resize_metadata_removed_by_default():
    response = client.post(
        "/api/v1/images/resize",
        files=[("files", ("test.png", _png_bytes(), "image/png"))],
        data={"resize_mode": "aspect", "width": "50", "remove_metadata": "true"},
    )
    assert response.status_code == 200


# ─── Image Cropper API tests ───────────────────────────────────


def test_api_crop_basic():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes((200, 100)), "image/png"))],
        data={
            "crop_x": "10",
            "crop_y": "10",
            "crop_width": "100",
            "crop_height": "50",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["width"] == 100
    assert body["height"] == 50


def test_api_crop_with_rotation():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes((100, 200)), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
            "rotation": "90",
        },
    )
    assert response.status_code == 200


def test_api_crop_with_flip():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes((100, 100)), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "100",
            "flip_horizontal": "true",
        },
    )
    assert response.status_code == 200
    assert response.json()["width"] == 50


def test_api_crop_preserves_transparency_png():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes((100, 100)), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
            "output_format": "png",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "png"
    assert body["details"]["has_alpha"] is True


def test_api_crop_jpeg_flattens_transparency():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes((100, 100)), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
            "output_format": "jpg",
            "background_color": "#ffffff",
        },
    )
    assert response.status_code == 200
    assert response.json()["format"] == "jpg"


def test_api_crop_rejects_negative_coords():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes(), "image/png"))],
        data={
            "crop_x": "-5",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
        },
    )
    assert response.status_code == 400


def test_api_crop_rejects_invalid_rotation():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes(), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
            "rotation": "45",
        },
    )
    assert response.status_code == 400


def test_api_crop_rejects_invalid_format():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes(), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
            "output_format": "tiff",
        },
    )
    assert response.status_code == 400


def test_api_crop_rejects_non_image():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("doc.txt", b"hello", "text/plain"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "50",
            "crop_height": "50",
        },
    )
    assert response.status_code == 415


def test_api_crop_auto_format_preserves_png():
    response = client.post(
        "/api/v1/tools/image/crop",
        files=[("file", ("photo.png", _png_bytes(), "image/png"))],
        data={
            "crop_x": "0",
            "crop_y": "0",
            "crop_width": "60",
            "crop_height": "40",
            "output_format": "auto",
        },
    )
    assert response.status_code == 200
    assert response.json()["format"] == "png"


def test_cover_crops_instead_of_stretching():
    """A preset of another shape must not squash the picture."""
    from PIL import Image

    from app.modules.image.services.resizer_service import image_resizer_service

    # A circle, twice as wide a canvas as it is tall.
    source = Image.new("RGB", (400, 200), "white")
    for x in range(400):
        for y in range(200):
            if (x - 200) ** 2 + (y - 100) ** 2 <= 80 ** 2:
                source.putpixel((x, y), (0, 0, 0))
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    result = image_resizer_service.resize(
        buffer.getvalue(),
        resize_mode="exact",
        width=100,
        height=100,
        output_format="png",
        allow_upscale=True,
        cover=True,
    )
    output = Image.open(BytesIO(result["data"])).convert("L")
    assert output.size == (100, 100)
    dark_columns = [x for x in range(100) if output.getpixel((x, 50)) < 128]
    dark_rows = [y for y in range(100) if output.getpixel((50, y)) < 128]
    # Still round: as wide as it is tall, and centred.
    assert abs(len(dark_columns) - len(dark_rows)) <= 2
    assert abs(dark_columns[0] - (99 - dark_columns[-1])) <= 2
