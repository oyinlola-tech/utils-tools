"""QR code generation for the qr-generator tool."""

import time
from io import BytesIO

from PIL import Image, ImageColor

from app.core.logging import get_tool_logger

MAX_BOX_SIZE = 30
MAX_BORDER = 16
SUPPORTED_QR_FORMATS = {"png", "webp", "svg"}


def _validate_color(value: str, label: str) -> str:
    """Accept any colour Pillow understands and return it as #rrggbb.

    Normalising also keeps user input out of the generated SVG markup.
    """
    try:
        red, green, blue = ImageColor.getrgb((value or "").strip())[:3]
    except ValueError as error:
        raise ValueError(f"Invalid {label} colour: {value!r}.") from error
    return f"#{red:02x}{green:02x}{blue:02x}"


class QrService:
    """Generate QR codes with optional logo overlay."""

    def generate_qr(
        self,
        content: str,
        box_size: int = 10,
        border: int = 4,
        fill_color: str = "#163300",
        back_color: str = "#ffffff",
        output_format: str = "png",
        image_data: bytes | None = None,
    ) -> tuple[bytes, str]:
        tool_logger = get_tool_logger("qr-generator")
        started = time.monotonic()
        import qrcode

        if not content.strip():
            raise ValueError("QR code content cannot be empty.")
        output_format = (output_format or "png").lower()
        if output_format not in SUPPORTED_QR_FORMATS:
            raise ValueError("Output format must be png, webp or svg.")
        if not 1 <= box_size <= MAX_BOX_SIZE:
            raise ValueError(f"Box size must be between 1 and {MAX_BOX_SIZE}.")
        if not 0 <= border <= MAX_BORDER:
            raise ValueError(f"Border must be between 0 and {MAX_BORDER}.")
        fill_color = _validate_color(fill_color, "fill")
        back_color = _validate_color(back_color, "background")

        factory = self._build(qrcode, content, box_size, border)

        if output_format == "svg":
            return self._make_svg(
                factory, box_size, fill_color, back_color, started, tool_logger
            )

        img = factory.make_image(
            fill_color=fill_color,
            back_color=back_color,
        ).convert("RGBA")

        if image_data is not None:
            img = self._overlay_logo(img, image_data)

        buffer = BytesIO()
        if output_format == "webp":
            img.save(buffer, format="WEBP", quality=95)
            tool_logger.info(
                "generated qr (webp, %d bytes) in %.2fs",
                buffer.getbuffer().nbytes,
                time.monotonic() - started,
            )
            return buffer.getvalue(), "image/webp"
        img.save(buffer, format="PNG")
        tool_logger.info(
            "generated qr (png, %d bytes) in %.2fs",
            buffer.getbuffer().nbytes,
            time.monotonic() - started,
        )
        return buffer.getvalue(), "image/png"

    @staticmethod
    def _build(qrcode, content: str, box_size: int, border: int):
        factory = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        factory.add_data(content)
        try:
            factory.make(fit=True)
        except (ValueError, qrcode.exceptions.DataOverflowError) as error:
            raise ValueError(
                "The content is too long to fit in a QR code "
                "(about 2,300 characters at most)."
            ) from error
        return factory

    @staticmethod
    def _make_svg(
        factory,
        box_size: int,
        fill_color: str,
        back_color: str,
        started: float,
        tool_logger,
    ) -> tuple[bytes, str]:
        """Render the module matrix as a single-path SVG.

        qrcode's SvgPathImage ignores ``fill_color``/``back_color`` (it
        writes them out as bogus attributes and draws black on
        transparent), so the chosen colours never reached SVG output.
        """
        matrix = factory.get_matrix()
        size = len(matrix)
        segments = [
            f"M{x},{y}h1v1h-1z"
            for y, row in enumerate(matrix)
            for x, dark in enumerate(row)
            if dark
        ]
        pixels = size * box_size
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{pixels}" '
            f'height="{pixels}" viewBox="0 0 {size} {size}" '
            'shape-rendering="crispEdges">'
            f'<rect width="{size}" height="{size}" fill="{back_color}"/>'
            f'<path fill="{fill_color}" d="{"".join(segments)}"/>'
            "</svg>"
        )
        data = svg.encode("utf-8")
        tool_logger.info(
            "generated qr (svg, %d bytes) in %.2fs",
            len(data),
            time.monotonic() - started,
        )
        return data, "image/svg+xml"

    @staticmethod
    def _overlay_logo(img: Image.Image, image_data: bytes) -> Image.Image:
        try:
            logo = Image.open(BytesIO(image_data))
            if logo.width * logo.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError("logo too large")
            logo.load()
        except Exception as error:
            raise ValueError("The uploaded logo is not a valid image.") from error
        logo = logo.convert("RGBA")
        box = img.size[0] // 5
        logo.thumbnail((box, box), Image.Resampling.LANCZOS)
        pos = ((img.size[0] - logo.width) // 2, (img.size[1] - logo.height) // 2)
        img.paste(logo, pos, logo)
        return img


qr_service = QrService()
