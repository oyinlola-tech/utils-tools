"""Shared helpers for the devtools services."""

from PIL import Image, ImageColor


def normalize_color(
    value: str,
    label: str,
    allow_transparent: bool = False,
) -> str:
    """Validate a user colour and return it as ``#rrggbb``.

    Colours are interpolated into SVG markup, so anything Pillow cannot
    parse (including quote/tag injection) is rejected.
    """
    cleaned = (value or "").strip()
    if allow_transparent and cleaned.lower() in {"transparent", "none", ""}:
        return "transparent"
    try:
        red, green, blue = ImageColor.getrgb(cleaned)[:3]
    except ValueError as error:
        raise ValueError(f"Invalid {label} colour: {value!r}.") from error
    return f"#{red:02x}{green:02x}{blue:02x}"


def favicon_sizes(image: Image.Image, size: int) -> Image.Image:
    source = image.convert("RGBA")
    if size <= 32:
        preview = source.copy()
        preview.thumbnail((size * 2, size * 2))
        return preview.resize((size, size), Image.Resampling.LANCZOS)
    target = source.copy()
    target.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(
        target,
        ((size - target.width) // 2, (size - target.height) // 2),
    )
    return canvas


def barcode_factory(code_type: str):
    import barcode

    name = {
        "code128": "Code128",
        "ean13": "EAN13",
        "ean8": "EAN8",
        "upca": "UPCA",
        "code39": "Code39",
        "itf": "ITF",
    }.get(code_type)
    if name is None:
        raise ValueError(f"Unsupported barcode type: {code_type}")
    try:
        return getattr(barcode, name)
    except AttributeError as error:
        raise ValueError(f"Unsupported barcode type: {code_type}") from error
