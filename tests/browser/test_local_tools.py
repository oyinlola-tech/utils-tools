"""The tools that run in the browser must answer as the server does."""

import hashlib
import io
import math
import os
import zipfile

import pikepdf
import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat


def encoded(image: Image.Image, format: str, **options) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=format, **options)
    return buffer.getvalue()


def photo(width=1200, height=900) -> Image.Image:
    """Smooth colour with fine detail, like a camera picture."""
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line([(0, y), (width, y)], fill=(40 + y * 180 // height, 110, 200 - y * 120 // height))
    for index in range(40):
        x, y = (index * 197) % width, (index * 131) % height
        draw.ellipse((x, y, x + 90, y + 60), fill=((index * 53) % 255, (index * 29) % 255, 120))
    noise = Image.effect_noise((width, height), 12).convert("RGB")
    return Image.blend(image, noise, 0.05).filter(ImageFilter.GaussianBlur(0.7))


def logo(size=512) -> Image.Image:
    """Soft edges on a transparent background."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((size // 12, size // 12, size - size // 12, size - size // 12), fill=(22, 51, 0, 255))
    draw.ellipse((size // 3, size // 3, size - size // 3, size - size // 3), fill=(159, 232, 112, 180))
    return image.filter(ImageFilter.GaussianBlur(size / 200))


def flat(width=800, height=600) -> Image.Image:
    """Few colours and hard edges, like a screenshot."""
    image = Image.new("RGB", (width, height), (246, 247, 249))
    draw = ImageDraw.Draw(image)
    for index in range(30):
        x, y = (index * 97) % width, (index * 61) % height
        draw.rectangle(
            (x, y, x + width // 4, y + height // 12),
            fill=[(22, 51, 0), (94, 181, 255), (40, 44, 52)][index % 3],
        )
    return image


PHOTO_JPG = encoded(photo(), "JPEG", quality=92)
PHOTO_PNG = encoded(photo(600, 450), "PNG")
LOGO_PNG = encoded(logo(), "PNG")
FLAT_PNG = encoded(flat(), "PNG")


def jpg_file(data=PHOTO_JPG, name="photo.jpg", field="files"):
    return (field, name, data, "image/jpeg")


def png_file(data=PHOTO_PNG, name="picture.png", field="files"):
    return (field, name, data, "image/png")


def on_white(image: Image.Image) -> Image.Image:
    """As it is seen: what lies under transparent pixels does not count."""
    canvas = Image.new("RGBA", image.size, "white")
    return Image.alpha_composite(canvas, image.convert("RGBA")).convert("RGB")


def psnr(first: Image.Image, second: Image.Image) -> float:
    """Closeness of two images in decibels; 40 and up look identical."""
    assert first.size == second.size
    difference = ImageChops.difference(on_white(first), on_white(second))
    mean_square = sum(ImageStat.Stat(difference).sum2) / (first.width * first.height * 3)
    return 99.0 if mean_square == 0 else 10 * math.log10(255**2 / mean_square)


def opened(outcome, item) -> Image.Image:
    image = Image.open(io.BytesIO(outcome["downloads"][item["download_url"]]))
    image.load()
    return image


# ------------------------------------------------------------------ files


def test_zip_holds_every_file_intact(tools):
    big = os.urandom(3 * 1024 * 1024)
    files = [
        ("files", "notes.txt", b"hello\n" * 5000, "text/plain"),
        ("files", "notes.txt", b"a second file of the same name", "text/plain"),
        ("files", "Notes.TXT", b"and a third, differing only in case", "text/plain"),
        ("files", "résumé — final.pdf", b"%PDF-1.4 not really", "application/pdf"),
        ("files", "random.bin", big, "application/octet-stream"),
        ("files", "empty.dat", b"", "application/octet-stream"),
        ("files", "folder\\nested\\windows.txt", b"from a windows path", "text/plain"),
    ]
    outcome = tools.local("/tools/file/zip", files)
    result = outcome["result"]
    archive = zipfile.ZipFile(io.BytesIO(outcome["downloads"][result["download_url"]]))

    assert archive.testzip() is None
    assert archive.namelist() == [
        "notes.txt",
        "notes (2).txt",
        "Notes (3).TXT",
        "résumé — final.pdf",
        "random.bin",
        "empty.dat",
        "windows.txt",
    ]
    assert [archive.read(name) for name in archive.namelist()] == [data for _, _, data, _ in files]
    assert archive.getinfo("notes.txt").compress_size < 1000
    assert result["filename"] == "notes-archive.zip"
    assert result["details"] == {"file_count": 7}
    assert result["size_bytes"] == len(outcome["downloads"][result["download_url"]])


def test_zip_matches_the_servers_entry_names(tools):
    files = [
        ("files", "a.png", LOGO_PNG, "image/png"),
        ("files", "a.png", FLAT_PNG, "image/png"),
        ("files", "no-extension", b"x", "text/plain"),
        ("files", "no-extension", b"y", "text/plain"),
    ]
    names = []
    for outcome in (tools.local("/tools/file/zip", files), tools.server("/tools/file/zip", files)):
        data = outcome["downloads"][outcome["result"]["download_url"]]
        names.append(zipfile.ZipFile(io.BytesIO(data)).namelist())
    assert names[0] == names[1]


def test_duplicates_match_the_server(tools):
    files = [
        ("files", "one.png", LOGO_PNG, "image/png"),
        ("files", "two.png", FLAT_PNG, "image/png"),
        ("files", "copy of one.png", LOGO_PNG, "image/png"),
        ("files", "same size.bin", bytes(len(FLAT_PNG)), "application/octet-stream"),
        ("files", "three.txt", b"text", "text/plain"),
        ("files", "three again.txt", b"text", "text/plain"),
    ]
    local = tools.local("/tools/file/duplicates", files)["result"]
    assert local == tools.server("/tools/file/duplicates", files)["result"]
    assert [group["filenames"] for group in local] == [
        ["one.png", "copy of one.png"],
        ["three.txt", "three again.txt"],
    ]
    assert local[0]["hash"] == hashlib.sha256(LOGO_PNG).hexdigest()


def test_analysis_matches_the_server(tools):
    rotated = Image.Exif()
    rotated[0x0112] = 6
    files = [
        jpg_file(),
        ("files", "sideways.jpg", encoded(photo(300, 200), "JPEG", exif=rotated.tobytes()), "image/jpeg"),
        ("files", "progressive.jpg", encoded(photo(310, 170), "JPEG", progressive=True), "image/jpeg"),
        png_file(LOGO_PNG),
        ("files", "lossy.webp", encoded(photo(320, 240), "WEBP", quality=80), "image/webp"),
        ("files", "lossless.webp", encoded(flat(330, 250), "WEBP", lossless=True), "image/webp"),
        ("files", "alpha.webp", encoded(logo(64), "WEBP", quality=80), "image/webp"),
        ("files", "anim.gif", encoded(flat(120, 90), "GIF"), "image/gif"),
        ("files", "bitmap.bmp", encoded(flat(130, 70), "BMP"), "image/bmp"),
        ("files", "renamed.png", b"this is text, whatever the name says", "image/png"),
        ("files", "notes.txt", b"plain text", "text/plain"),
    ]
    local = tools.local("/tools/file/analyze", files)["result"]
    assert local == tools.server("/tools/file/analyze", files)["result"]
    assert (local["files"][1]["width"], local["files"][1]["height"]) == (300, 200)


@pytest.mark.parametrize(
    "extra",
    [
        ("files", "document.pdf", None, "application/pdf"),
        ("files", "scan.tiff", encoded(flat(100, 80), "TIFF"), "image/tiff"),
        ("files", "empty.txt", b"", "text/plain"),
    ],
)
def test_analysis_leaves_what_it_cannot_read_to_the_server(tools, extra):
    field, name, data, content_type = extra
    if data is None:
        document = pikepdf.new()
        document.add_blank_page()
        buffer = io.BytesIO()
        document.save(buffer)
        data = buffer.getvalue()
    outcome = tools.local("/tools/file/analyze", [png_file(), (field, name, data, content_type)])
    assert outcome["result"] is None


# ----------------------------------------------------------------- images


@pytest.mark.parametrize("target", ["jpg", "webp", "png"])
@pytest.mark.parametrize(
    "source",
    [jpg_file(), png_file(), png_file(LOGO_PNG, "logo.png"), png_file(FLAT_PNG, "flat.png")],
    ids=["photo.jpg", "photo.png", "logo.png", "flat.png"],
)
def test_conversion_matches_the_server(tools, source, target):
    fields = {"output_format": target, "remove_metadata": True}
    local = tools.local("/images/convert", [source], fields)
    server = tools.server("/images/convert", [source], fields)
    mine, theirs = local["result"]["results"][0], server["result"]["results"][0]

    for key in ("original_filename", "input_format", "output_format", "width", "height",
                "original_width", "original_height", "original_size_bytes"):
        assert mine[key] == theirs[key], key
    assert mine["details"]["flattened"] == theirs["details"]["flattened"]
    assert mine["output_filename"] == source[1].rsplit(".", 1)[0] + f".{target}"
    assert local["result"]["successful_files"] == 1 and local["result"]["failures"] == []

    image, reference = opened(local, mine), opened(server, theirs)
    assert image.format == reference.format
    assert mine["size_bytes"] == len(local["downloads"][mine["download_url"]])
    assert psnr(image, reference) >= 38
    if target != "jpg":
        assert image.convert("RGBA").getchannel("A").getextrema() == (
            reference.convert("RGBA").getchannel("A").getextrema()
        )
    # No larger than the server's by more than a third.
    assert mine["size_bytes"] <= theirs["size_bytes"] * 1.35


def test_png_output_is_lossless_and_compact(tools):
    # Each is written in the smallest form that holds it.
    for data, mode in ((PHOTO_PNG, "RGB"), (LOGO_PNG, "RGBA"), (FLAT_PNG, "P")):
        outcome = tools.local("/images/convert", [png_file(data)], {"output_format": "png"})
        item = outcome["result"]["results"][0]
        image = opened(outcome, item)
        source = Image.open(io.BytesIO(data))
        assert image.mode == mode
        assert ImageChops.difference(image.convert("RGBA"), source.convert("RGBA")).getbbox() is None
        assert item["size_bytes"] <= len(encoded(source, "PNG", optimize=True)) * 1.2


def test_transparency_is_filled_with_the_chosen_colour(tools):
    fields = {"output_format": "jpg", "background_color": "#ff0000"}
    outcome = tools.local("/images/convert", [png_file(LOGO_PNG, "logo.png")], fields)
    item = outcome["result"]["results"][0]
    image = opened(outcome, item).convert("RGB")
    assert item["details"] == {**item["details"], "flattened": True, "has_alpha": False}
    red, green, blue = image.getpixel((5, 5))
    assert red > 240 and green < 20 and blue < 20


def test_photos_come_out_the_right_way_up(tools):
    sideways = Image.Exif()
    sideways[0x0112] = 6
    source = jpg_file(encoded(photo(400, 200), "JPEG", quality=92, exif=sideways.tobytes()))
    fields = {"output_format": "jpg"}
    local = tools.local("/images/convert", [source], fields)
    server = tools.server("/images/convert", [source], fields)
    mine, theirs = local["result"]["results"][0], server["result"]["results"][0]
    assert (mine["width"], mine["height"]) == (theirs["width"], theirs["height"]) == (200, 400)
    image = opened(local, mine)
    assert image.getexif().get(0x0112) is None
    assert psnr(image, opened(server, theirs)) >= 38


RESIZES = [
    {"resize_mode": "aspect", "width": 300},
    {"resize_mode": "aspect", "height": 225},
    {"resize_mode": "aspect", "width": 5000},
    {"resize_mode": "aspect", "width": 2000, "allow_upscale": True},
    {"resize_mode": "aspect", "width": 333, "height": 111},
    {"resize_mode": "exact", "width": 640, "height": 360},
    {"resize_mode": "percent", "percent": 50},
    {"resize_mode": "percent", "percent": 12.5},
    {"resize_mode": "percent", "percent": 150},
    {"resize_mode": "percent", "percent": 150, "allow_upscale": True},
    {"resize_mode": "max", "max_width": 500},
    {"resize_mode": "max", "max_width": 300, "max_height": 700},
    {"resize_mode": "max", "max_height": 5000},
    {"resize_mode": "max", "max_width": 1800, "allow_upscale": True},
    {"resize_mode": "aspect", "width": 301, "output_format": "webp", "quality": 80},
    {"resize_mode": "aspect", "width": 301, "output_format": "jpeg", "quality": 70},
    {"resize_mode": "aspect", "width": 301, "output_format": "png"},
]


@pytest.mark.parametrize("fields", RESIZES, ids=lambda fields: "-".join(map(str, fields.values())))
def test_resizing_matches_the_server(tools, fields):
    files = [jpg_file(), png_file(LOGO_PNG, "logo.png")]
    local = tools.local("/images/resize", files, fields)
    server = tools.server("/images/resize", files, fields)
    assert local["result"]["successful_files"] == server["result"]["successful_files"] == 2

    for mine, theirs in zip(local["result"]["results"], server["result"]["results"]):
        for key in ("input_format", "output_format", "width", "height", "original_width", "original_height"):
            assert mine[key] == theirs[key], key
        assert {**mine["details"], "has_alpha": None} == {**theirs["details"], "has_alpha": None}
        image, reference = opened(local, mine), opened(server, theirs)
        assert image.size == (mine["width"], mine["height"])
        assert image.format == reference.format
        assert psnr(image, reference) >= 30
        assert mine["size_bytes"] <= theirs["size_bytes"] * 1.35 + 2048


@pytest.mark.parametrize(
    "fields",
    [
        {"resize_mode": "aspect"},
        {"resize_mode": "exact", "width": 100},
        {"resize_mode": "aspect", "width": 0},
        {"resize_mode": "aspect", "width": -5},
        {"resize_mode": "aspect", "width": 9000},
        {"resize_mode": "percent", "percent": 0},
        {"resize_mode": "percent", "percent": 20000},
        {"resize_mode": "diagonal", "width": 100},
        {"resize_mode": "aspect", "width": 100, "output_format": "avif"},
        {"resize_mode": "aspect", "width": 100, "quality": 0},
        {"resize_mode": "aspect", "width": 100, "background_color": "papayawhip"},
    ],
    ids=lambda fields: "-".join(map(str, fields.values())),
)
def test_requests_the_server_would_refuse_are_left_to_it(tools, fields):
    assert tools.local("/images/resize", [jpg_file()], fields)["result"] is None


@pytest.mark.parametrize(
    ("source", "fields"),
    [
        (jpg_file(), {"output_format": "avif"}),
        (jpg_file(), {"output_format": "webp", "lossless": "true"}),
        (jpg_file(), {"output_format": "jpg", "remove_metadata": False}),
        (jpg_file(), {"output_format": "gif"}),
        (("files", "scan.tiff", encoded(flat(100, 80), "TIFF"), "image/tiff"), {"output_format": "png"}),
        (("files", "old.gif", encoded(flat(100, 80), "GIF"), "image/gif"), {"output_format": "png"}),
        (("files", "renamed.jpg", b"not an image at all", "image/jpeg"), {"output_format": "png"}),
        (
            ("files", "moving.webp", encoded(flat(60, 40), "WEBP", save_all=True,
                                             append_images=[photo(60, 40)], duration=100), "image/webp"),
            {"output_format": "png"},
        ),
        (
            ("files", "moving.png", encoded(flat(60, 40), "PNG", save_all=True,
                                            append_images=[photo(60, 40)], duration=100), "image/png"),
            {"output_format": "jpg"},
        ),
    ],
    ids=["avif", "lossless", "keep-metadata", "gif-output", "tiff", "gif", "not-an-image",
         "animated-webp", "animated-png"],
)
def test_conversions_the_browser_cannot_do_are_left_to_the_server(tools, source, fields):
    assert tools.local("/images/convert", [source], fields)["result"] is None


def test_one_unsupported_file_sends_the_whole_batch_to_the_server(tools):
    files = [jpg_file(), ("files", "scan.tiff", encoded(flat(100, 80), "TIFF"), "image/tiff")]
    assert tools.local("/images/convert", files, {"output_format": "png"})["result"] is None


def test_images_too_large_for_a_canvas_are_left_to_the_server(tools):
    huge = encoded(Image.new("RGB", (4200, 4000), (10, 20, 30)), "PNG")
    assert tools.local("/images/convert", [png_file(huge)], {"output_format": "jpg"})["result"] is None


@pytest.mark.parametrize(
    ("size", "output"),
    [((1080, 1080), "png"), ((1200, 630), "jpg"), ((1080, 1920), "webp"), ((1500, 500), "jpg")],
)
def test_presets_are_filled_without_stretching(tools, size, output):
    fields = {"width": size[0], "height": size[1], "cover": True, "output_format": output}
    source = ("file", "photo.jpg", PHOTO_JPG, "image/jpeg")
    local = tools.local("/tools/image/resize", [source], fields)
    server = tools.server("/tools/image/resize", [source], fields)
    mine, theirs = local["result"], server["result"]

    for key in ("original_filename", "width", "height", "format"):
        assert mine[key] == theirs[key], key
    assert set(mine["details"]) == set(theirs["details"])
    image, reference = opened(local, mine), opened(server, theirs)
    assert image.size == size
    assert psnr(image, reference) >= 30


def test_metadata_is_removed_without_an_upload(tools):
    exif = Image.Exif()
    exif[0x010F] = "Camera maker"
    exif[0x0112] = 8
    tagged = encoded(photo(400, 300), "JPEG", quality=92, exif=exif.tobytes(), dpi=(300, 300),
                     comment=b"taken at home")
    source = ("file", "holiday.jpg", tagged, "image/jpeg")
    local = tools.local("/tools/image/remove-metadata", [source])
    server = tools.server("/tools/image/remove-metadata", [source])
    mine, theirs = local["result"], server["result"]

    assert mine["details"]["removed_metadata"] == theirs["details"]["removed_metadata"]
    assert "exif" in mine["details"]["removed_metadata"]
    for key in ("original_filename", "width", "height", "format"):
        assert mine[key] == theirs[key], key
    image = opened(local, mine)
    assert image.size == (300, 400)
    assert not image.getexif() and "comment" not in image.info
    assert psnr(image, opened(server, theirs)) >= 38


@pytest.mark.parametrize(
    "source",
    [
        ("file", "plain.jpg", encoded(photo(200, 150), "JPEG"), "image/jpeg"),
        ("file", "print.png", encoded(flat(200, 150), "PNG", dpi=(300, 300)), "image/png"),
        ("file", "plain.png", LOGO_PNG, "image/png"),
        ("file", "plain.webp", encoded(photo(200, 150), "WEBP", quality=90), "image/webp"),
    ],
    ids=lambda source: source[1],
)
def test_reported_metadata_matches_the_server(tools, source):
    local = tools.local("/tools/image/remove-metadata", [source])["result"]
    server = tools.server("/tools/image/remove-metadata", [source])["result"]
    assert local["details"]["removed_metadata"] == server["details"]["removed_metadata"]
    assert local["format"] == server["format"]
