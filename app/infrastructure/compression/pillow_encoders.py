"""PIL format encoders."""

from io import BytesIO

from PIL import Image

from app.infrastructure.compression.pillow_utils import (
    filter_metadata,
    parse_color,
)

# Exhaustive settings cost far more time than they save in bytes: on a
# 12 megapixel photo, PNG at zlib level 9 takes twelve times as long as
# level 6 for a file 14% smaller, and WebP method 6 on an image with
# transparency takes fourteen times as long as method 4 for 20%. Only
# the compressor, where size is the point, asks for ``smallest``.
_PNG_OPTIMIZE_MAX_PIXELS = 2_000_000
_PNG_LEVEL = 6
_WEBP_METHOD = 4
_WEBP_METHOD_SMALLEST = 6


def encode_png(
    image: Image.Image,
    strip_metadata: bool = True,
    smallest: bool = False,
) -> bytes:
    output = BytesIO()
    try:
        save_kwargs = filter_metadata(image, strip=strip_metadata)
        if smallest or image.width * image.height <= _PNG_OPTIMIZE_MAX_PIXELS:
            save_kwargs["optimize"] = True
        else:
            save_kwargs["compress_level"] = _PNG_LEVEL
        image.save(
            output,
            format="PNG",
            **save_kwargs,
        )
        return output.getvalue()
    finally:
        output.close()


def encode_webp(
    image: Image.Image,
    quality: int = 95,
    strip_metadata: bool = True,
    lossless: bool = False,
    smallest: bool = False,
) -> bytes:
    output = BytesIO()
    try:
        save_kwargs = filter_metadata(image, strip=strip_metadata)
        if lossless:
            image.save(
                output,
                format="WEBP",
                lossless=True,
                **save_kwargs,
            )
        else:
            image.save(
                output,
                format="WEBP",
                quality=quality,
                method=_WEBP_METHOD_SMALLEST if smallest else _WEBP_METHOD,
                **save_kwargs,
            )
        return output.getvalue()
    finally:
        output.close()


def encode_jpeg(
    image: Image.Image,
    quality: int = 95,
    strip_metadata: bool = True,
    background_color: str | None = None,
) -> bytes:
    if image.mode in ("RGBA", "LA", "P"):
        bg = parse_color(background_color)
        background = Image.new("RGB", image.size, bg)
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    output = BytesIO()
    try:
        save_kwargs = filter_metadata(image, strip=strip_metadata)
        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            **save_kwargs,
        )
        return output.getvalue()
    finally:
        output.close()


def encode_avif(
    image: Image.Image,
    quality: int = 85,
    strip_metadata: bool = True,
) -> bytes:
    if image.mode not in ("RGBA", "RGB", "LA"):
        image = image.convert("RGBA")
    output = BytesIO()
    try:
        save_kwargs = filter_metadata(image, strip=strip_metadata)
        image.save(
            output,
            format="AVIF",
            quality=quality,
            **save_kwargs,
        )
        return output.getvalue()
    finally:
        output.close()
