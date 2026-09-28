"""Facade over the PIL image encoders."""

from PIL import Image

from app.infrastructure.compression.pillow_encoders import (
    encode_avif,
    encode_jpeg,
    encode_png,
    encode_webp,
)
from app.infrastructure.compression.pillow_utils import (
    parse_color,
)


class PillowAdapter:

    def _filter_metadata(self, image, strip):
        from app.infrastructure.compression.pillow_utils import (
            filter_metadata,
        )

        return filter_metadata(image, strip)

    def encode_png(
        self,
        image: Image.Image,
        strip_metadata: bool = True,
        smallest: bool = False,
    ) -> bytes:
        return encode_png(
            image,
            strip_metadata=strip_metadata,
            smallest=smallest,
        )

    def encode_webp(
        self,
        image: Image.Image,
        quality: int = 95,
        strip_metadata: bool = True,
        lossless: bool = False,
        smallest: bool = False,
    ) -> bytes:
        return encode_webp(
            image,
            quality=quality,
            strip_metadata=strip_metadata,
            lossless=lossless,
            smallest=smallest,
        )

    def encode_jpeg(
        self,
        image: Image.Image,
        quality: int = 95,
        strip_metadata: bool = True,
        background_color: str | None = None,
    ) -> bytes:
        return encode_jpeg(
            image,
            quality=quality,
            strip_metadata=strip_metadata,
            background_color=background_color,
        )

    def encode_avif(
        self,
        image: Image.Image,
        quality: int = 85,
        strip_metadata: bool = True,
    ) -> bytes:
        return encode_avif(
            image,
            quality=quality,
            strip_metadata=strip_metadata,
        )

    def encode(
        self,
        image: Image.Image,
        output_format: str,
        quality: int = 92,
        strip_metadata: bool = True,
        lossless: bool = False,
        background_color: str | None = None,
    ) -> tuple[bytes, str]:
        output_format = output_format.lower()
        if output_format in {"jpg", "jpeg"}:
            return (
                self.encode_jpeg(
                    image,
                    quality=quality,
                    strip_metadata=strip_metadata,
                    background_color=background_color,
                ),
                "image/jpeg",
            )
        if output_format == "png":
            return (
                self.encode_png(
                    image,
                    strip_metadata=strip_metadata,
                ),
                "image/png",
            )
        if output_format == "webp":
            return (
                self.encode_webp(
                    image,
                    quality=quality,
                    strip_metadata=strip_metadata,
                    lossless=lossless,
                ),
                "image/webp",
            )
        if output_format == "avif":
            return (
                self.encode_avif(
                    image,
                    quality=quality,
                    strip_metadata=strip_metadata,
                ),
                "image/avif",
            )
        raise ValueError(f"Unsupported output format: {output_format}")


pillow_adapter = PillowAdapter()
_parse_color = parse_color
