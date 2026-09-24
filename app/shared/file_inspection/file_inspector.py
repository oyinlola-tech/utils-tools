from dataclasses import dataclass

from app.shared.file_inspection.file_types import (
    FileCategory,
)


@dataclass(frozen=True)
class FileInspectionResult:
    category: FileCategory
    mime_type: str
    extension: str
    is_supported: bool


FILE_SIGNATURES = {
    b"\xFF\xD8\xFF": (
        FileCategory.IMAGE,
        "image/jpeg",
        ".jpg",
    ),
    b"\x89PNG\r\n\x1a\n": (
        FileCategory.IMAGE,
        "image/png",
        ".png",
    ),
    b"GIF87a": (
        FileCategory.IMAGE,
        "image/gif",
        ".gif",
    ),
    b"GIF89a": (
        FileCategory.IMAGE,
        "image/gif",
        ".gif",
    ),
    b"BM": (
        FileCategory.IMAGE,
        "image/bmp",
        ".bmp",
    ),
    b"II*\x00": (
        FileCategory.IMAGE,
        "image/tiff",
        ".tiff",
    ),
    b"MM\x00*": (
        FileCategory.IMAGE,
        "image/tiff",
        ".tiff",
    ),
    b"%PDF-": (
        FileCategory.PDF,
        "application/pdf",
        ".pdf",
    ),
}


class FileInspector:
    def inspect(
        self,
        file_data: bytes,
    ) -> FileInspectionResult:
        if not file_data:
            return FileInspectionResult(
                category=FileCategory.UNKNOWN,
                mime_type="application/octet-stream",
                extension="",
                is_supported=False,
            )

        for signature, (
            category,
            mime_type,
            extension,
        ) in FILE_SIGNATURES.items():
            if file_data.startswith(signature):
                return FileInspectionResult(
                    category=category,
                    mime_type=mime_type,
                    extension=extension,
                    is_supported=True,
                )

        if (
            file_data.startswith(b"RIFF")
            and len(file_data) >= 12
            and file_data[8:12] == b"WEBP"
        ):
            return FileInspectionResult(
                category=FileCategory.IMAGE,
                mime_type="image/webp",
                extension=".webp",
                is_supported=True,
            )

        if _is_avif(file_data):
            return FileInspectionResult(
                category=FileCategory.IMAGE,
                mime_type="image/avif",
                extension=".avif",
                is_supported=True,
            )

        return FileInspectionResult(
            category=FileCategory.UNKNOWN,
            mime_type="application/octet-stream",
            extension="",
            is_supported=False,
        )


_AVIF_BRANDS = {b"avif", b"avis"}


def _is_avif(file_data: bytes) -> bool:
    """Detect AVIF from its ISO-BMFF ``ftyp`` box (major or compatible brand)."""
    if len(file_data) < 16 or file_data[4:8] != b"ftyp":
        return False
    box_size = int.from_bytes(file_data[0:4], "big")
    box_end = min(max(box_size, 16), len(file_data), 256)
    if file_data[8:12] in _AVIF_BRANDS:
        return True
    brands = file_data[16:box_end]
    return any(
        brands[offset:offset + 4] in _AVIF_BRANDS
        for offset in range(0, len(brands) - 3, 4)
    )


file_inspector = FileInspector()
