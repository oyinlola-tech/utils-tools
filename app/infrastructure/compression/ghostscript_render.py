"""PDF-to-image rendering via PyMuPDF pixmaps."""

from app.infrastructure.compression.ghostscript_utils import (
    get_pymupdf,
)

# Every rendered page is held in memory until the response is built.
MAX_RENDER_PAGES = 200
# A page with a huge MediaBox at high DPI could otherwise ask MuPDF for
# a multi-GB pixmap and take the process down.
MAX_PAGE_PIXELS = 100_000_000


def render_pages(
    file_data: bytes,
    image_format: str = "png",
    dpi: int = 150,
) -> list[tuple[str, bytes]]:
    image_format = image_format.lower()
    if image_format not in {"png", "jpeg"}:
        raise ValueError(
            "Image format must be png or jpeg."
        )
    pymupdf = get_pymupdf()
    try:
        document = pymupdf.open(
            stream=file_data,
            filetype="pdf",
        )
    except Exception as error:
        raise RuntimeError(
            f"Unable to open PDF: {error}"
        ) from error
    try:
        if document.needs_pass:
            raise ValueError(
                "This PDF is password-protected. Remove the password and try again."
            )
        if document.page_count > MAX_RENDER_PAGES:
            raise ValueError(
                f"This PDF has {document.page_count} pages; at most "
                f"{MAX_RENDER_PAGES} pages can be converted at once. "
                "Split it first."
            )
        pages: list[tuple[str, bytes]] = []
        for index, page in enumerate(
            document,
            start=1,
        ):
            scale = dpi / 72
            pixels = (page.rect.width * scale) * (page.rect.height * scale)
            if pixels > MAX_PAGE_PIXELS:
                raise ValueError(
                    f"Page {index} is too large to render at {dpi} DPI; "
                    "choose a lower DPI."
                )
            pixmap = page.get_pixmap(
                dpi=dpi,
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            if image_format == "png":
                data = pixmap.tobytes("png")
                extension = "png"
            else:
                data = pixmap.tobytes(
                    "jpeg",
                    jpg_quality=90,
                )
                extension = "jpg"
            pages.append(
                (
                    f"page-{index:03d}.{extension}",
                    data,
                )
            )
    finally:
        document.close()
    if not pages:
        raise RuntimeError(
            "PDF to image conversion produced no pages."
        )
    return pages
