"""Safe, normalised image loading shared by every image tool.

Every tool used to call ``Image.open(...).load()`` directly, which
meant:

* EXIF orientation was ignored, so phone photos came out rotated once
  metadata was stripped (the default everywhere);
* 16-bit grayscale PNG/TIFF (``I;16``/``I``) were clipped to pure white
  on conversion to 8-bit modes;
* CMYK and other exotic modes crashed PNG/WebP encoders;
* images between ``MAX_IMAGE_PIXELS`` and twice that only raised a
  warning and were fully decoded, allowing multi-GB allocations.
"""

from io import BytesIO

from PIL import Image, ImageOps

_HIGH_BIT_DEPTH_MODES = {"I;16", "I;16L", "I;16B", "I;16N", "I"}
_KEEP_MODES = {"1", "L", "LA", "P", "RGB", "RGBA"}


class ImageTooLargeError(ValueError):
    """Raised when an image's pixel count exceeds the safe limit."""


def check_pixel_limit(image: Image.Image) -> None:
    limit = Image.MAX_IMAGE_PIXELS
    if limit and image.width * image.height > limit:
        raise ImageTooLargeError(
            f"Image dimensions {image.width}x{image.height} are too large "
            f"(maximum {limit // 1_000_000} megapixels)."
        )


def normalize_mode(image: Image.Image) -> Image.Image:
    """Convert modes the encoders cannot handle into 8-bit equivalents."""
    mode = image.mode
    if mode in _KEEP_MODES:
        return image
    if mode in _HIGH_BIT_DEPTH_MODES:
        # Scale 16-bit samples down instead of clipping them at 255.
        return image.point(lambda value: value / 256).convert("L")
    if mode == "F":
        low, high = image.getextrema()
        span = (high - low) or 1
        return image.point(lambda value: (value - low) * 255 / span).convert("L")
    if mode == "PA":
        return image.convert("RGBA")
    if mode in {"RGBa", "La"}:
        return image.convert("RGBA" if mode == "RGBa" else "LA")
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    return image.convert("RGBA" if has_alpha else "RGB")


def load_image(
    file_data: bytes,
    *,
    transpose: bool = True,
    normalize: bool = True,
) -> Image.Image:
    """Open, bound-check, decode and orient an uploaded image.

    Raises ``ValueError`` (``ImageTooLargeError`` for oversized images)
    so callers can map it to a 4xx response.
    """
    try:
        image = Image.open(BytesIO(file_data))
    except Image.DecompressionBombError as error:
        raise ImageTooLargeError(
            "Image dimensions are too large to process."
        ) from error
    except (OSError, SyntaxError) as error:
        raise ValueError("The uploaded file is not a valid image.") from error
    check_pixel_limit(image)
    source_format = image.format
    try:
        image.load()
    except Image.DecompressionBombError as error:
        raise ImageTooLargeError(
            "Image dimensions are too large to process."
        ) from error
    except (OSError, SyntaxError) as error:
        raise ValueError(
            "The image could not be decoded; it may be corrupt or truncated."
        ) from error
    frame_count = getattr(image, "n_frames", 1)
    if transpose:
        transposed = ImageOps.exif_transpose(image)
        if transposed is not None and transposed is not image:
            transposed.format = source_format
            image = transposed
    if normalize:
        normalized = normalize_mode(image)
        if normalized is not image:
            normalized.info = dict(image.info)
            normalized.format = source_format
            image = normalized
    if frame_count > 1 and getattr(image, "n_frames", 1) != frame_count:
        # Keep animation detection working on derived images.
        image.n_frames = frame_count
    return image
