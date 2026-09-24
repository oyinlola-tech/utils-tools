"""Regression tests for the bug-hunt fixes (tools, storage, security)."""

import os
import time
import zipfile
from io import BytesIO

import pikepdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.infrastructure.storage import storage
from app.main import app
from app.modules.pdf.services.pdf_page_utils import parse_page_selection
from app.shared.utils.file_util import sanitize_filename, unique_filename
from app.shared.utils.image_util import ImageTooLargeError, load_image

client = TestClient(app)


# ---------------------------------------------------------------- helpers


def _pdf_bytes(pages: int = 1) -> bytes:
    buffer = BytesIO()
    frames = [Image.new("RGB", (100, 100), "white") for _ in range(pages)]
    frames[0].save(buffer, format="PDF", save_all=True, append_images=frames[1:])
    return buffer.getvalue()


def _encrypted_pdf() -> bytes:
    buffer = BytesIO()
    with pikepdf.open(BytesIO(_pdf_bytes())) as pdf:
        pdf.save(buffer, encryption=pikepdf.Encryption(user="pw", owner="pw"))
    return buffer.getvalue()


def _image_bytes(image: Image.Image, fmt: str, **kwargs) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def _png(mode: str = "RGB", size=(40, 30), color="red") -> bytes:
    return _image_bytes(Image.new(mode, size, color), "PNG")


def _download(url: str) -> bytes:
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.content


# ------------------------------------------------------- page selection


@pytest.mark.parametrize(
    ("spec", "count", "expected"),
    [
        ("1-3", 1, [1]),
        ("1-3", 2, [1, 2]),
        ("all", 3, [1, 2, 3]),
        ("", 2, [1, 2]),
        ("2-", 4, [2, 3, 4]),
        ("-2", 4, [1, 2]),
        ("3, 1, 1-2", 5, [1, 2, 3]),
        ("1-999999999", 2, [1, 2]),
    ],
)
def test_parse_page_selection_clamps_and_defaults(spec, count, expected):
    assert parse_page_selection(spec, count) == expected


@pytest.mark.parametrize("spec", ["5", "4-6", "abc", "3-1", "0", "1-2-3"])
def test_parse_page_selection_rejects_invalid(spec):
    with pytest.raises(ValueError, match="Invalid page"):
        parse_page_selection(spec, 3)


def test_pdf_extract_default_range_works_for_short_pdf():
    response = client.post(
        "/api/v1/tools/pdf/extract",
        files={"file": ("one.pdf", _pdf_bytes(1), "application/pdf")},
        data={"pages": "1-3"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["details"]["page_count"] == 1

    # The pages field is optional and means "all pages".
    response = client.post(
        "/api/v1/tools/pdf/extract",
        files={"file": ("two.pdf", _pdf_bytes(2), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["details"]["page_count"] == 2


# --------------------------------------------------- encrypted/corrupt PDF


@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/api/v1/tools/pdf/split", {}),
        ("/api/v1/tools/pdf/rotate", {}),
        ("/api/v1/tools/pdf/extract", {}),
        ("/api/v1/tools/pdf/info", {}),
        ("/api/v1/tools/pdf/encrypt", {"password": "x"}),
        ("/api/v1/tools/pdf/to-images", {}),
    ],
)
def test_encrypted_and_corrupt_pdfs_return_400(path, data):
    encrypted = client.post(
        path,
        files={"file": ("secret.pdf", _encrypted_pdf(), "application/pdf")},
        data=data,
    )
    assert encrypted.status_code == 400
    assert "password-protected" in encrypted.json()["error"]["message"]

    corrupt = client.post(
        path,
        files={
            "file": (
                "broken.pdf",
                b"%PDF-1.4\n garbage \n%%EOF\n",
                "application/pdf",
            )
        },
        data=data,
    )
    assert corrupt.status_code == 400
    assert "damaged" in corrupt.json()["error"]["message"]


def test_merge_rejects_encrypted_pdf_with_400():
    response = client.post(
        "/api/v1/tools/pdf/merge",
        files=[
            ("files", ("a.pdf", _pdf_bytes(), "application/pdf")),
            ("files", ("b.pdf", _encrypted_pdf(), "application/pdf")),
        ],
    )
    assert response.status_code == 400
    assert "b.pdf" in response.json()["error"]["message"]


def test_page_number_rejects_unknown_position():
    response = client.post(
        "/api/v1/tools/pdf/page-number",
        files={"file": ("a.pdf", _pdf_bytes(), "application/pdf")},
        data={"position": "nowhere"},
    )
    assert response.status_code == 400


def test_pdf_render_rejects_too_many_pages(monkeypatch):
    from app.infrastructure.compression import ghostscript_render

    monkeypatch.setattr(ghostscript_render, "MAX_RENDER_PAGES", 2)
    with pytest.raises(ValueError, match="at most 2 pages"):
        ghostscript_render.render_pages(_pdf_bytes(3))


# -------------------------------------------------------- output names


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a/b.pdf", "b.pdf"),
        ("..\\..\\win.zip", "win.zip"),
        ("<img src=x onerror=alert(1)>.png", "img_src_x_onerror_alert_1.png"),
        ("ünïcödé 文件.pdf", "unicode.pdf"),
        ("..", "file"),
        ("report.final.pdf", "report.final.pdf"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_unique_filename_never_fails_on_hostile_names():
    name = unique_filename('"quo\'te/../x' * 40 + ".pdf")
    assert name.endswith(".pdf")
    assert len(name) < 160
    assert all(ch.isalnum() or ch in "._-" for ch in name)


def test_tool_with_path_in_upload_name_succeeds():
    response = client.post(
        "/api/v1/tools/pdf/rotate",
        files={"file": ("dir/sub/doc.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["filename"].startswith("doc-rotated_")


# ---------------------------------------------------- QR / barcode / SVG


def test_qr_and_barcode_have_download_filenames():
    qr = client.post("/api/v1/tools/dev/qr", data={"content": "hi"})
    assert qr.status_code == 200
    assert qr.headers["content-disposition"] == 'attachment; filename="qr-code.png"'

    qr_svg = client.post(
        "/api/v1/tools/dev/qr",
        data={"content": "hi", "output_format": "svg"},
    )
    assert qr_svg.headers["content-disposition"].endswith('qr-code.svg"')

    barcode = client.post(
        "/api/v1/tools/dev/barcode",
        data={"content": "12345", "output_format": "webp"},
    )
    assert barcode.status_code == 200
    assert barcode.headers["content-disposition"] == (
        'attachment; filename="barcode-code128.webp"'
    )


def test_qr_svg_uses_chosen_colors():
    response = client.post(
        "/api/v1/tools/dev/qr",
        data={
            "content": "hello",
            "output_format": "svg",
            "fill_color": "#ff0000",
            "back_color": "#00ff00",
        },
    )
    assert response.status_code == 200
    svg = response.text
    assert 'fill="#ff0000"' in svg
    assert 'fill="#00ff00"' in svg
    assert "fill_color" not in svg


@pytest.mark.parametrize(
    "data",
    [
        {"content": "x", "fill_color": '"/><script>alert(1)</script>'},
        {"content": "x" * 5000},
        {"content": "x", "box_size": "1000"},
        {"content": "x", "output_format": "gif"},
    ],
)
def test_qr_rejects_bad_input_with_400(data):
    response = client.post("/api/v1/tools/dev/qr", data=data)
    assert response.status_code == 400


def _svg_upload(content: bytes, precision: str | None = None):
    data = {"precision": precision} if precision is not None else {}
    return client.post(
        "/api/v1/tools/dev/svg-optimize",
        files={"file": ("logo.svg", content, "image/svg+xml")},
        data=data,
    )


def test_svg_optimizer_honours_precision_and_keeps_document_valid():
    source = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10.5 10.25">'
        b'<image href="data:image/png;base64,iVBOR+007/1e5A"/>'
        b'<path d="M1.23456 2.5L1.5.5"/></svg>'
    )
    two = _svg_upload(source, "2")
    zero = _svg_upload(source, "0")
    keep = _svg_upload(source, "-1")
    assert two.status_code == zero.status_code == keep.status_code == 200
    assert two.headers["content-disposition"] == (
        'attachment; filename="logo.min.svg"'
    )
    assert 'version="1.0"' in two.text  # XML declaration untouched
    assert "iVBOR+007/1e5A" in two.text  # data URI untouched
    assert 'd="M1.23 2.5L1.5.5"' in two.text
    assert 'd="M1 2L2 0"' in zero.text  # numbers stay separated
    assert 'd="M1.23456 2.5L1.5.5"' in keep.text


def test_svg_optimizer_rejects_bad_precision_and_non_svg():
    assert _svg_upload(b"<svg xmlns='http://www.w3.org/2000/svg'/>", "99").status_code == 400
    assert _svg_upload(b"<html></html>").status_code == 400
    assert _svg_upload(b"\xff\xfe\x00").status_code == 400


def test_svg_generator_rejects_markup_in_colors():
    response = client.post(
        "/api/v1/tools/dev/svg-generate",
        files={"image": ("a.png", _png(), "image/png")},
        data={"foreground_color": '"/><script>alert(1)</script>'},
    )
    assert response.status_code == 400


def test_favicon_png_is_named_after_its_real_size():
    response = client.post(
        "/api/v1/tools/dev/favicon",
        files={"image": ("a.png", _png(size=(64, 64)), "image/png")},
        data={"size": "16"},
    )
    assert response.status_code == 200
    names = zipfile.ZipFile(BytesIO(response.content)).namelist()
    assert "favicon-16x16.png" in names


def test_json_tools_keep_unicode_and_union_keys():
    formatted = client.post(
        "/api/v1/tools/dev/json-format",
        json={"json_text": '{"name": "café ☕"}'},
    )
    assert "café ☕" in formatted.json()["result"]

    csv_response = client.post(
        "/api/v1/tools/dev/json-to-csv",
        json={"data": '[{"a": 1}, {"b": {"c": 2}}]'},
    )
    assert csv_response.status_code == 200
    lines = csv_response.json()["csv"].splitlines()
    assert lines[0] == "a,b"
    assert lines[2] == ',"{""c"": 2}"'


# ------------------------------------------------------- image decoding


def test_load_image_applies_exif_orientation():
    image = Image.new("RGB", (80, 40), "blue")
    exif = image.getexif()
    exif[0x0112] = 6  # rotate 90 CW on display
    data = _image_bytes(image, "JPEG", exif=exif.tobytes())
    assert load_image(data).size == (40, 80)


def test_load_image_scales_16_bit_and_converts_cmyk():
    gray16 = load_image(_png("I;16", color=40000))
    assert gray16.mode == "L"
    assert gray16.getpixel((0, 0)) == 156  # not clipped to 255

    cmyk = load_image(_image_bytes(Image.new("CMYK", (8, 8), (0, 128, 255, 0)), "JPEG"))
    assert cmyk.mode == "RGB"


def test_load_image_rejects_pixel_bombs(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ImageTooLargeError):
        load_image(_png(size=(20, 20)))


def test_oversized_dimensions_return_413(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    response = client.post(
        "/api/v1/tools/image/convert",
        files={"file": ("big.png", _png(size=(60, 60)), "image/png")},
        data={"output_format": "jpg"},
    )
    assert response.status_code == 413


def test_converter_handles_orientation_16bit_and_cmyk():
    rotated = Image.new("RGB", (80, 40), "blue")
    exif = rotated.getexif()
    exif[0x0112] = 6
    cases = [
        (_image_bytes(rotated, "JPEG", exif=exif.tobytes()), "png", (40, 80)),
        (_png("I;16", color=40000), "jpg", (40, 30)),
        (_image_bytes(Image.new("CMYK", (8, 8)), "JPEG"), "png", (8, 8)),
    ]
    for data, fmt, size in cases:
        response = client.post(
            "/api/v1/tools/image/convert",
            files={"file": ("in.bin", data, "application/octet-stream")},
            data={"output_format": fmt},
        )
        assert response.status_code == 200, response.text
        result = Image.open(BytesIO(_download(response.json()["download_url"])))
        assert result.size == size


def test_avif_and_tiff_uploads_are_accepted():
    for fmt in ("AVIF", "TIFF"):
        data = _image_bytes(Image.new("RGB", (20, 20), "red"), fmt)
        response = client.post(
            "/api/v1/tools/image/convert",
            files={"file": (f"a.{fmt.lower()}", data, "image/x")},
            data={"output_format": "png"},
        )
        assert response.status_code == 200, (fmt, response.text)


def test_image_to_pdf_flattens_transparency_onto_white():
    from app.modules.pdf.services.pdf_from_images_service import _as_pdf_page

    page = _as_pdf_page(_png("RGBA", color=(255, 0, 0, 0)))
    assert page.mode == "RGB"
    assert page.getpixel((0, 0)) == (255, 255, 255)


def test_batch_convert_rejects_unknown_background_color():
    response = client.post(
        "/api/v1/images/convert",
        files=[("files", ("t.png", _png("RGBA", color=(0, 0, 0, 0)), "image/png"))],
        data={"output_format": "jpg", "background_color": "notacolor"},
    )
    assert response.status_code == 400


def test_palette_rejects_out_of_range_colour_count():
    response = client.post(
        "/api/v1/tools/image/palette-extractor",
        files={"file": ("a.png", _png(), "image/png")},
        data={"num_colors": "500"},
    )
    assert response.status_code == 400


# ------------------------------------------------------------ compression


@pytest.mark.parametrize(
    "data",
    [
        {"output_format": "gif"},
        {"compression_preset": "weird"},
        {"max_dimension": "-5"},
        {"target_size": "0"},
    ],
)
def test_compression_rejects_bad_options_before_creating_job(data):
    response = client.post(
        "/api/v1/images/compress",
        files=[("files", ("a.png", _png(), "image/png"))],
        data=data,
    )
    assert response.status_code == 400


def test_compression_accepts_jpg_alias():
    response = client.post(
        "/api/v1/images/compress",
        files=[("files", ("a.png", _png(), "image/png"))],
        data={"output_format": "jpg"},
    )
    assert response.status_code == 200


# -------------------------------------------------------------- archives


def test_zip_creator_keeps_files_with_duplicate_names():
    response = client.post(
        "/api/v1/tools/file/zip",
        files=[
            ("files", ("a.txt", b"one", "text/plain")),
            ("files", ("a.txt", b"two", "text/plain")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"].count("_") == 1  # a single uniqueness token
    archive = zipfile.ZipFile(BytesIO(_download(body["download_url"])))
    assert sorted(archive.namelist()) == ["a (2).txt", "a.txt"]


# ------------------------------------------------------ request handling


def test_request_body_limit_returns_413(monkeypatch):
    monkeypatch.setattr(settings, "max_request_body_mb", 1)
    response = client.post(
        "/api/v1/tools/pdf/info",
        files={"file": ("a.pdf", b"x" * (2 * 1024 * 1024), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_rate_limiter_evicts_idle_clients():
    from app.core import middleware

    middleware._RATE_LIMIT_BUCKETS.clear()
    now = time.monotonic()
    middleware._RATE_LIMIT_BUCKETS["old"] = middleware.deque([now - 1000])
    middleware._RATE_LIMIT_BUCKETS["active"] = middleware.deque([now])
    middleware._evict_idle_buckets(now, 60)
    assert set(middleware._RATE_LIMIT_BUCKETS) == {"active"}
    middleware._RATE_LIMIT_BUCKETS.clear()


def test_background_job_registry_is_bounded():
    from app.modules.background.routes import background_route_helpers as helpers

    helpers.background_jobs.clear()
    for _ in range(helpers.MAX_RECORDED_JOBS + 25):
        helpers.record_job({})
    assert len(helpers.background_jobs) == helpers.MAX_RECORDED_JOBS
    helpers.background_jobs.clear()


# ------------------------------------------------------- cleanup sweeper


def test_cleanup_sweeps_expired_outputs():
    from app.modules.jobs.job_cleanup_service import job_cleanup_service

    storage.processed_path.mkdir(parents=True, exist_ok=True)
    storage.compressed_path.mkdir(parents=True, exist_ok=True)
    old_output = storage.processed_path / "sweep-old-test.png"
    old_compressed = storage.compressed_path / "sweep-old-test.webp"
    fresh_output = storage.processed_path / "sweep-fresh-test.png"
    for path in (old_output, old_compressed, fresh_output):
        path.write_bytes(b"data")
    expired = time.time() - (settings.job_ttl_minutes + 5) * 60
    os.utime(old_output, (expired, expired))
    os.utime(old_compressed, (expired, expired))
    placeholder = storage.processed_path / ".gitkeep-sweep-test"
    placeholder.write_bytes(b"")
    os.utime(placeholder, (expired, expired))
    try:
        removed = job_cleanup_service.cleanup_expired_outputs()
        assert removed >= 2
        assert not old_output.exists()
        assert not old_compressed.exists()
        assert fresh_output.exists()
        assert placeholder.exists()  # dotfiles such as .gitkeep are kept
    finally:
        fresh_output.unlink(missing_ok=True)
        placeholder.unlink(missing_ok=True)


def test_cleanup_sweep_is_throttled():
    from app.modules.jobs.job_cleanup_service import JobCleanupService

    service = JobCleanupService()
    assert service.claim_sweep() is True
    assert service.claim_sweep() is False  # already running
    service.run_claimed_sweep()
    assert service.claim_sweep() is False  # within the interval


# --------------------------------------------------- Vercel large download


def test_large_downloads_redirect_to_blob_on_vercel(monkeypatch, tmp_path):
    from app.shared.utils import download_util

    big = tmp_path / "big.png"
    big.write_bytes(b"0" * (download_util.VERCEL_RESPONSE_LIMIT_BYTES + 1))
    small = tmp_path / "small.png"
    small.write_bytes(b"0")
    monkeypatch.setattr(settings, "storage_driver", "vercel")
    monkeypatch.setattr(settings, "blob_access_mode", "public")
    monkeypatch.setattr(
        download_util.storage,
        "get_url",
        lambda path: f"https://blob.example/{path.name}",
    )

    redirect = download_util.download_response(big, "image/png")
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://blob.example/big.png?download=1"

    streamed = download_util.download_response(small, "image/png")
    assert streamed.status_code == 200

    monkeypatch.setattr(settings, "storage_driver", "local")
    assert download_util.download_response(big, "image/png").status_code == 200
