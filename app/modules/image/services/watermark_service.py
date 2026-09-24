"""Watermark overlay logic for the watermark tool."""

import time

from PIL import Image, ImageDraw

from app.core.logging import get_tool_logger
from app.infrastructure.compression.pillow_adapter import pillow_adapter
from app.modules.image.services.image_helpers import (
    POSITION_ALIASES,
    default_font,
    open_image,
)
from app.shared.utils.image_util import load_image


class WatermarkService:
    """Overlay a text or logo watermark onto an image."""

    def add_watermark(
        self,
        file_data: bytes,
        text: str | None = None,
        logo_data: bytes | None = None,
        position: str = "bottom-right",
        opacity: float = 0.7,
        size_ratio: float = 0.1,
        rotation: int = 0,
    ) -> dict:
        """Overlay a text or logo watermark onto an image."""
        tool_logger = get_tool_logger("watermark")
        started = time.monotonic()
        image = open_image(file_data).convert("RGBA")

        if text:
            layer = self._build_text_layer(
                image, text, opacity, size_ratio, rotation
            )
        elif logo_data:
            layer = self._build_logo_layer(
                image, logo_data, opacity, size_ratio, rotation
            )
        else:
            raise ValueError("Provide watermark text or a logo image.")

        positioned = self._place(image, layer, position)
        result = Image.alpha_composite(image, positioned)
        data = pillow_adapter.encode_webp(result, quality=95)
        tool_logger.info(
            "watermarked %dx%d image (%s, %d bytes) in %.2fs",
            image.width, image.height,
            "text" if text else "logo",
            len(data), time.monotonic() - started,
        )
        return {"data": data, "content_type": "image/webp", "extension": "webp", "width": image.width, "height": image.height}

    def _build_text_layer(
        self,
        image: Image.Image,
        text: str,
        opacity: float,
        size_ratio: float,
        rotation: int,
    ) -> Image.Image:
        font_size = max(10, round(min(image.size) * size_ratio))
        font = default_font(font_size)
        text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        bbox = text_draw.textbbox((0, 0), text, font=font)
        x = (image.width - (bbox[2] - bbox[0])) // 2
        y = (image.height - (bbox[3] - bbox[1])) // 2
        text_draw.text(
            (x - bbox[0], y - bbox[1]),
            text,
            font=font,
            fill=(255, 255, 255, round(255 * opacity)),
        )
        if rotation:
            text_layer = text_layer.rotate(
                rotation,
                expand=True,
                resample=Image.Resampling.BICUBIC,
            )
        return text_layer

    def _build_logo_layer(
        self,
        image: Image.Image,
        logo_data: bytes,
        opacity: float,
        size_ratio: float,
        rotation: int,
    ) -> Image.Image:
        try:
            logo = load_image(logo_data)
        except Exception as error:
            raise ValueError("The uploaded watermark logo is not a valid image.") from error
        logo = logo.convert("RGBA")
        target = max(16, round(min(image.size) * size_ratio))
        logo.thumbnail((target, target), Image.Resampling.LANCZOS)
        if logo.mode == "RGBA":
            alpha = logo.getchannel("A").point(
                lambda value: round(value * opacity)
            )
            logo.putalpha(alpha)
        if rotation:
            logo = logo.rotate(
                rotation,
                expand=True,
                resample=Image.Resampling.BICUBIC,
            )
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        x = (image.width - logo.width) // 2
        y = (image.height - logo.height) // 2
        layer.paste(logo, (x, y), logo)
        return layer

    def _place(
        self,
        image: Image.Image,
        watermark: Image.Image,
        position: str,
    ) -> Image.Image:
        anchor = POSITION_ALIASES.get(position)
        if anchor is None:
            raise ValueError(f"Unknown watermark position: {position}")
        horizontal, vertical = anchor

        canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        margin = max(12, round(min(image.size) * 0.04))
        x = self._axis(horizontal, image.width, watermark.width, margin)
        y = self._axis(vertical, image.height, watermark.height, margin)
        canvas.paste(watermark, (x, y), watermark)
        return canvas
    @staticmethod
    def _axis(
        alignment: str,
        canvas_size: int,
        item_size: int,
        margin: int,
    ) -> int:
        if alignment == "left":
            return margin
        if alignment == "right":
            return canvas_size - item_size - margin
        return (canvas_size - item_size) // 2


watermark_service = WatermarkService()
