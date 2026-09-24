MAX_FILENAME_LENGTH = 255
DEFAULT_OUTPUT_FORMAT = "png"
MAX_FILES_PER_BATCH = 20

SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".avif",
    ".bmp",
    ".tiff",
    ".tif",
}

SUPPORTED_PDF_EXTENSIONS = {
    ".pdf",
}

SUPPORTED_ARCHIVE_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".7z",
}

# Detected extension per MIME type, used to cross-check uploads
# against the filename claimed by the client.
EXPECTED_EXTENSION_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/avif": ".avif",
    "application/pdf": ".pdf",
}
