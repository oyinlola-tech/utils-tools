"""Unit tests for the image tools service (Phase 4)."""

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.modules.background.background_service import background_service
from app.modules.image.image_service import image_service


def _png_bytes(size=(120, 80), color=(255, 0, 0, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpg_bytes(size=(120, 80)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (10, 200, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_convert_png_to_jpg_flattens_transparency():
    result = image_service.convert(_png_bytes(), "jpg")
    assert result["extension"] == "jpg"
    assert result["content_type"] == "image/jpeg"
    assert result["flattened"] is True


def test_convert_to_avif():
    result = image_service.convert(_png_bytes(), "avif")
    assert result["content_type"] == "image/avif"
    assert result["flattened"] is False


def test_convert_rejects_unknown_format():
    try:
        image_service.convert(_png_bytes(), "tiff")
    except ValueError as error:
        assert "Unsupported" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_resize_by_percent_keeps_aspect():
    result = image_service.resize(_png_bytes(), resize_mode="percent", percent=50)
    assert result["width"] == 60
    assert result["height"] == 40


def test_resize_to_exact_box():
    result = image_service.resize(
        _png_bytes(),
        resize_mode="exact",
        width=100,
        height=100,
        maintain_aspect_ratio=False,
    )
    assert result["width"] == 100
    assert result["height"] == 100


def test_resize_aspect_width_only():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="aspect",
        width=100,
    )
    assert result["width"] == 100
    assert result["height"] == 50


def test_resize_aspect_height_only():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="aspect",
        height=50,
    )
    assert result["width"] == 100
    assert result["height"] == 50


def test_resize_max_dimension_shrinks_longer_edge():
    result = image_service.resize(
        _png_bytes((400, 200)),
        resize_mode="max",
        max_dimension=200,
    )
    assert result["width"] == 200
    assert result["height"] == 100


def test_resize_max_dimension_no_upscale():
    result = image_service.resize(
        _png_bytes((100, 100)),
        resize_mode="max",
        max_dimension=500,
        allow_upscale=False,
    )
    assert result["width"] == 100
    assert result["height"] == 100


def test_resize_max_dimension_with_upscale():
    result = image_service.resize(
        _png_bytes((100, 100)),
        resize_mode="max",
        max_dimension=500,
        allow_upscale=True,
    )
    assert result["width"] == 500
    assert result["height"] == 500


def test_resize_requires_an_option():
    try:
        image_service.resize(_png_bytes(), resize_mode="aspect")
    except ValueError as error:
        assert "Provide" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_remove_metadata_reencodes_cleanly():
    result = image_service.remove_metadata(_jpg_bytes())
    assert result["extension"] == "jpg"
    assert isinstance(result["removed_metadata"], list)
    assert result["width"] == 120


def test_add_text_watermark():
    result = image_service.add_watermark(
        _png_bytes(),
        text="UTILS TOOLS",
        position="center",
    )
    assert result["extension"] == "webp"
    assert result["width"] == 120


def test_add_logo_watermark():
    result = image_service.add_watermark(
        _png_bytes(),
        logo_data=_png_bytes((20, 20)),
        rotation=45,
    )
    assert result["extension"] == "webp"


def test_watermark_requires_text_or_logo():
    try:
        image_service.add_watermark(_png_bytes())
    except ValueError as error:
        assert "Provide" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_watermark_rejects_bad_position():
    try:
        image_service.add_watermark(
            _png_bytes(),
            text="x",
            position="middle",
        )
    except ValueError as error:
        assert "position" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_background_replacement_with_color():
    image, width, height = background_service.replace_background(
        _png_bytes(),
        color="#00ff00",
    )
    assert (width, height) == (120, 80)
    assert image.size == (120, 80)


def test_background_replacement_with_image():
    image, _width, _height = background_service.replace_background(
        _png_bytes(),
        image_data=_png_bytes((40, 40)),
    )
    assert image.size == (120, 80)


def test_background_replacement_rejects_bad_image():
    try:
        background_service.replace_background(
            _png_bytes(),
            image_data=b"not an image",
        )
    except ValueError as error:
        assert "not valid" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_crop_basic():
    result = image_service.crop(
        _png_bytes(),
        crop_x=10,
        crop_y=10,
        crop_width=50,
        crop_height=50,
    )
    assert result["width"] == 50
    assert result["height"] == 50
    assert result["extension"] == "png"


def test_crop_top_left():
    result = image_service.crop(
        _png_bytes(size=(100, 100)),
        crop_x=0,
        crop_y=0,
        crop_width=20,
        crop_height=20,
    )
    assert result["width"] == 20
    assert result["height"] == 20


def test_crop_center_4_3_ratio():
    result = image_service.crop(
        _png_bytes(size=(400, 300)),
        crop_x=50,
        crop_y=25,
        crop_width=300,
        crop_height=225,
    )
    assert result["width"] == 300
    assert result["height"] == 225


def test_crop_rotation_90():
    result = image_service.crop(
        _png_bytes(size=(100, 200)),
        crop_x=10,
        crop_y=10,
        crop_width=50,
        crop_height=50,
        rotation=90,
    )
    assert result["width"] == 50
    assert result["height"] == 50


def test_crop_flip_horizontal():
    result = image_service.crop(
        _png_bytes(size=(100, 100)),
        crop_x=0,
        crop_y=0,
        crop_width=50,
        crop_height=100,
        flip_horizontal=True,
    )
    assert result["width"] == 50
    assert result["height"] == 100


def test_crop_flip_vertical():
    result = image_service.crop(
        _png_bytes(size=(100, 100)),
        crop_x=0,
        crop_y=0,
        crop_width=50,
        crop_height=100,
        flip_vertical=True,
    )
    assert result["width"] == 50
    assert result["height"] == 100


def test_crop_rotation_and_flip():
    result = image_service.crop(
        _png_bytes(size=(100, 200)),
        crop_x=10,
        crop_y=10,
        crop_width=50,
        crop_height=50,
        rotation=180,
        flip_horizontal=True,
    )
    assert result["width"] == 50
    assert result["height"] == 50


def test_crop_preserves_transparency():
    result = image_service.crop(
        _png_bytes(),
        crop_x=0,
        crop_y=0,
        crop_width=60,
        crop_height=40,
        output_format="png",
    )
    assert result["has_alpha"] is True
    assert result["flattened"] is False


def test_crop_jpeg_flattens_transparency():
    result = image_service.crop(
        _png_bytes(),
        crop_x=0,
        crop_y=0,
        crop_width=60,
        crop_height=40,
        output_format="jpg",
        background_color="#ffffff",
    )
    assert result["extension"] == "jpg"
    assert result["flattened"] is True


def test_crop_removes_metadata():
    original = _png_bytes(size=(100, 100), color=(255, 0, 0, 255))
    result = image_service.crop(
        original,
        crop_x=0,
        crop_y=0,
        crop_width=50,
        crop_height=50,
        strip_metadata=True,
    )
    assert "exif" not in Image.open(BytesIO(result["data"])).info


def test_crop_invalid_format():
    try:
        image_service.crop(
            _png_bytes(),
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
            output_format="tiff",
        )
    except ValueError as error:
        assert "Unsupported" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_crop_out_of_bounds():
    try:
        image_service.crop(
            _png_bytes(size=(100, 100)),
            crop_x=50,
            crop_y=50,
            crop_width=200,
            crop_height=200,
        )
    except ValueError as error:
        assert "extends beyond" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_crop_negative_coordinates():
    try:
        image_service.crop(
            _png_bytes(),
            crop_x=-1,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
    except ValueError as error:
        assert "non-negative" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_crop_corrupted_image():
    try:
        image_service.crop(
            b"not an image",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
    except (OSError, ValueError, UnidentifiedImageError):
        pass
    else:
        raise AssertionError("Expected error for corrupted image")


def test_crop_rotation_180_dimensions_swap():
    result = image_service.crop(
        _png_bytes(size=(200, 100)),
        crop_x=0,
        crop_y=0,
        crop_width=50,
        crop_height=50,
        rotation=180,
    )
    assert result["width"] == 50
    assert result["height"] == 50


def test_fast_encoders_stay_close_to_the_smallest_output():
    """The default encoder settings trade a little size for a lot of time."""
    import os

    from PIL import Image

    from app.infrastructure.compression.pillow_adapter import pillow_adapter

    width, height = 1800, 1400
    photo = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    photo = photo.resize((width // 6, height // 6)).resize((width, height))

    for encode in (pillow_adapter.encode_png, pillow_adapter.encode_webp):
        fast = encode(photo)
        smallest = encode(photo, smallest=True)
        assert len(smallest) <= len(fast) <= len(smallest) * 1.25
        assert Image.open(BytesIO(fast)).size == (width, height)


def test_small_pngs_are_still_fully_optimized():
    from PIL import Image

    from app.infrastructure.compression.pillow_adapter import pillow_adapter

    icon = Image.new("RGBA", (256, 256), (20, 120, 200, 255))
    assert pillow_adapter.encode_png(icon) == pillow_adapter.encode_png(icon, smallest=True)
