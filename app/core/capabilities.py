"""Tool registry and environment capability detection.

The registry declares every tool the product ships, and each tool
declares whether it can actually run in the current environment.

Local deployments expose the full feature set. Vercel deployments
only expose features that the serverless runtime can honestly
execute. The frontend reads this data from ``GET /api/v1/capabilities``
and shows, hides, or disables tools accordingly.

No secrets are ever part of the capability payload.
"""

import importlib.util
import logging
import shutil
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_DRIVER = "local"
VERCEL_DRIVER = "vercel"
# Vercel Functions reject request bodies over 4.5 MB before the app sees
# them; 4 MB leaves room for multipart overhead.
VERCEL_MAX_UPLOAD_MB = 4

CATEGORY_IMAGE = "image"
CATEGORY_PDF = "pdf"
CATEGORY_FILE = "file"
CATEGORY_DEVELOPER = "developer"
CATEGORY_UTILITY = "utility"
CATEGORY_TEXT = "text"


@dataclass(frozen=True)
class Tool:
    """Declarative description of a single tool."""

    id: str
    name: str
    category: str
    description: str
    # "available" | "planned"
    status: str = "planned"
    # drivers in which the tool is usable ("local", "vercel")
    environments: tuple[str, ...] = (LOCAL_DRIVER,)
    max_upload_mb: int | None = None
    max_files: int = 1
    notes: str = ""
    # runtime dependency that must exist for the tool to work
    requires_binary: str | None = None
    requires_module: str | None = None
    # whether the tool is surfaced on the landing page as a featured entry
    featured: bool = False


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _binary_available(binary_name: str) -> bool:
    return shutil.which(binary_name) is not None


class CapabilityRegistry:
    def __init__(self) -> None:
        self.driver: str = settings.storage_driver
        self.tools: tuple[Tool, ...] = self._build_registry()

    @staticmethod
    def _build_registry() -> tuple[Tool, ...]:
        return (
            # ------------------------------------------------- image
            Tool(
                id="background-remover",
                name="Background Remover",
                category=CATEGORY_IMAGE,
                description=(
                    "Remove image backgrounds and download "
                    "transparent PNG or WebP results."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Powered by rembg; model is loaded lazily.",
                requires_module="rembg",
                featured=True,
            ),
            Tool(
                id="image-compressor",
                name="Image Compressor",
                category=CATEGORY_IMAGE,
                description=(
                    "Compress JPG, PNG, WebP and AVIF images "
                    "with quality presets and target-size control."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                max_files=20,
            ),
            Tool(
                id="pdf-compressor",
                name="PDF Compressor",
                category=CATEGORY_PDF,
                description=(
                    "Reduce PDF file size with maximum, balanced "
                    "or high-quality modes."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
                max_files=20,
                notes="Pure-Python compression via PyMuPDF.",
                requires_module="pymupdf",
                featured=True,
            ),
            Tool(
                id="image-converter",
                name="Image Converter",
                category=CATEGORY_IMAGE,
                description=(
                    "Convert between JPG, PNG, WebP and AVIF "
                    "while preserving quality and transparency."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                featured=True,
            ),
            Tool(
                id="image-resizer",
                name="Image Resizer",
                category=CATEGORY_IMAGE,
                description=(
                    "Resize images by dimensions, percentage or "
                    "maximum size with aspect-ratio control."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                max_files=50,
                featured=True,
            ),
            Tool(
                id="image-cropper",
                name="Image Cropper",
                category=CATEGORY_IMAGE,
                description=(
                    "Crop, rotate and flip images with precise "
                    "coordinate mapping and export in JPG, PNG or WebP."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Runs in the browser with backend validation.",
                featured=True,
            ),
            Tool(
                id="image-editor",
                name="Image Editor",
                category=CATEGORY_IMAGE,
                description=(
                    "Adjust brightness, contrast, saturation, "
                    "sharpness and more with a live preview."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Runs entirely in the browser.",
            ),
            Tool(
                id="metadata-remover",
                name="Metadata Remover",
                category=CATEGORY_IMAGE,
                description=(
                    "Strip EXIF, GPS and other hidden metadata "
                    "from images explicitly."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
            ),
            Tool(
                id="watermark",
                name="Image Watermark",
                category=CATEGORY_IMAGE,
                description=(
                    "Add text or logo watermarks with position, "
                    "opacity, size and rotation control."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
            ),
            Tool(
                id="background-replacement",
                name="Background Replacement",
                category=CATEGORY_IMAGE,
                description=(
                    "Remove an image background and place it on "
                    "a solid color or another image."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Depends on the background-removal engine.",
                requires_module="rembg",
            ),
            # --------------------------------------------------- pdf
            Tool(
                id="pdf-merger",
                name="PDF Merger",
                category=CATEGORY_PDF,
                description=(
                    "Combine multiple PDFs into one document "
                    "with drag-and-drop ordering."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
                max_files=10,
                featured=True,
            ),
            Tool(
                id="pdf-splitter",
                name="PDF Splitter",
                category=CATEGORY_PDF,
                description=(
                    "Split a PDF by page ranges or selected pages "
                    "and download individual files or a ZIP."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
            ),
            Tool(
                id="pdf-to-image",
                name="PDF to Image",
                category=CATEGORY_PDF,
                description=(
                    "Convert PDF pages to JPG or PNG with quality "
                    "and DPI options."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
                notes="Rendered with PyMuPDF, no external binaries.",
                requires_module="pymupdf",
            ),
            Tool(
                id="image-to-pdf",
                name="Image to PDF",
                category=CATEGORY_PDF,
                description=(
                    "Turn one or many images into a single PDF "
                    "with ordering and orientation control."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                max_files=20,
            ),
            Tool(
                id="pdf-rotator",
                name="PDF Rotator",
                category=CATEGORY_PDF,
                description=(
                    "Rotate a PDF or selected pages by 90, 180 "
                    "or 270 degrees."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
            ),
            Tool(
                id="pdf-extractor",
                name="PDF Page Extractor",
                category=CATEGORY_PDF,
                description=(
                    "Extract selected pages or ranges into a new "
                    "PDF document."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=50,
            ),
            # --------------------------------------------------- file
            Tool(
                id="file-analyzer",
                name="File Analyzer",
                category=CATEGORY_FILE,
                description=(
                    "Inspect files: type, size, hash, dimensions, "
                    "PDF page count and metadata."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_files=20,
                featured=True,
            ),
            Tool(
                id="zip-creator",
                name="ZIP Creator",
                category=CATEGORY_FILE,
                description=(
                    "Package multiple files into a single ZIP "
                    "archive for batch download."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_files=50,
            ),
            Tool(
                id="duplicate-finder",
                name="Duplicate Finder",
                category=CATEGORY_FILE,
                description=(
                    "Hash files in a batch to find and group "
                    "identical duplicates."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_files=50,
            ),
            # ---------------------------------------------- developer
            Tool(
                id="favicon-generator",
                name="Favicon Generator",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Generate a full favicon set (ICO, PNG) from "
                    "one image."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
            ),
            Tool(
                id="svg-optimizer",
                name="SVG Optimizer",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Minify SVG files while preserving visual output."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=10,
            ),
            Tool(
                id="svg-generator",
                name="SVG Generator",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Convert raster images (PNG, JPG, WebP) into "
                    "scalable SVG path graphics with threshold control."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=10,
                requires_module="potrace",
            ),
            Tool(
                id="image-to-base64",
                name="Image to Base64",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Convert an image to raw Base64 or a data URI."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Runs entirely in the browser.",
            ),
            Tool(
                id="base64-to-image",
                name="Base64 to Image",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Decode raw Base64 or data URIs back into "
                    "PNG, JPG or WebP files."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Runs entirely in the browser.",
            ),
            Tool(
                id="qr-generator",
                name="QR Code Generator",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Generate QR codes for URLs, text, email, "
                    "phone or WiFi with live preview."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=5,
            ),
            Tool(
                id="barcode-generator",
                name="Barcode Generator",
                category=CATEGORY_DEVELOPER,
                description=(
                    "Generate Code 128, EAN-13 and UPC barcodes "
                    "with format validation."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=5,
            ),
            # ------------------------------------------------ utility
            Tool(
                id="social-media-resizer",
                name="Social Media Resizer",
                category=CATEGORY_UTILITY,
                description=(
                    "Resize and crop images to the current "
                    "dimensions for Instagram, YouTube, Facebook, "
                    "LinkedIn, X and TikTok."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
            ),
            Tool(
                id="screenshot-beautifier",
                name="Screenshot Beautifier",
                category=CATEGORY_UTILITY,
                description=(
                    "Frame screenshots with rounded corners, "
                    "padding, shadows and device frames."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                max_upload_mb=25,
                notes="Runs entirely in the browser.",
            ),
            Tool(
                id="video-downloader",
                name="Video Downloader",
                category=CATEGORY_UTILITY,
                description=(
                    "Download videos from YouTube, TikTok (no watermark), "
                    "Facebook, Instagram, Twitter/X and more."
                ),
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                requires_module="yt_dlp",
                featured=True,
            ),
            # --- New PDF Tools ---
            Tool(
                id="pdf-encrypt",
                name="PDF Password Protect",
                category=CATEGORY_PDF,
                description="Encrypt PDF files with user and owner passwords.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                requires_module="pikepdf",
            ),
            Tool(
                id="pdf-page-number",
                name="PDF Page Numberer",
                category=CATEGORY_PDF,
                description="Add page numbers to PDF documents.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                requires_module="fitz",
            ),
            Tool(
                id="pdf-watermark",
                name="PDF Watermark",
                category=CATEGORY_PDF,
                description="Add text watermark overlay to PDF pages.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                requires_module="fitz",
            ),
            # --- New Dev & Data Tools ---
            Tool(
                id="json-csv-converter",
                name="JSON / CSV Converter",
                category=CATEGORY_DEVELOPER,
                description="Convert JSON data to CSV spreadsheets and vice versa.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            Tool(
                id="json-formatter",
                name="JSON Formatter & Minifier",
                category=CATEGORY_DEVELOPER,
                description="Format, validate, or minify JSON data.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            Tool(
                id="jwt-decoder",
                name="JWT Decoder",
                category=CATEGORY_DEVELOPER,
                description="Decode JSON Web JWT headers and payloads safely.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            # --- New Text & Audio Tools ---
            Tool(
                id="text-diff",
                name="Text Diff Tool",
                category=CATEGORY_TEXT,
                description="Compare two texts side-by-side and highlight differences.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            Tool(
                id="case-converter",
                name="Text Case Converter",
                category=CATEGORY_TEXT,
                description="Convert text between camelCase, snake_case, UPPERCASE, etc.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            Tool(
                id="word-counter",
                name="Word & Character Counter",
                category=CATEGORY_TEXT,
                description="Count words, characters, sentences, and reading time.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
            Tool(
                id="text-to-speech",
                name="Text-to-Speech",
                category=CATEGORY_TEXT,
                description="Convert text input into downloadable MP3 audio speech.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
                requires_module="gtts",
            ),
            # --- New Image Tools ---
            Tool(
                id="palette-extractor",
                name="Color Palette Extractor",
                category=CATEGORY_IMAGE,
                description="Extract dominant HEX color codes from photos.",
                status="available",
                environments=(LOCAL_DRIVER, VERCEL_DRIVER),
            ),
        )

    @property
    def is_vercel(self) -> bool:
        return self.driver == VERCEL_DRIVER

    def system_capabilities(self) -> dict:
        """Runtime capabilities of the host, not user-facing tool claims."""
        pdf_compression = _module_available("pymupdf")
        background_removal = _module_available("rembg")
        return {
            "local_processing": True,
            "background_removal": background_removal,
            "pdf_compression": pdf_compression,
            "zip_support": True,
            "max_upload_size_mb": self.upload_limit_mb(
                settings.max_upload_size_mb
            ),
        }

    def upload_limit_mb(self, limit_mb: int) -> int:
        if self.driver == VERCEL_DRIVER:
            return min(limit_mb, VERCEL_MAX_UPLOAD_MB)
        return limit_mb

    def dependencies_satisfied(self, tool: Tool) -> bool:
        if tool.requires_binary and not _binary_available(
            tool.requires_binary
        ):
            return False
        return not (tool.requires_module and not _module_available(tool.requires_module))

    def effective_tools(self) -> list[dict]:
        """Tools visible in the current environment.

        Planned tools are listed with ``status: "planned"`` so the
        frontend can show them as coming soon, but they are never
        advertised as usable. Implemented tools are only advertised
        when their runtime dependencies are actually present.
        """
        driver = self.driver
        tools = []
        for tool in self.tools:
            available = (
                tool.status == "available"
                and driver in tool.environments
                and self.dependencies_satisfied(tool)
            )
            if available:
                status_label = "available"
            elif tool.status == "planned":
                status_label = "planned"
            else:
                status_label = "unavailable"
            tools.append(
                {
                    "id": tool.id,
                    "name": tool.name,
                    "category": tool.category,
                    "description": tool.description,
                    "status": status_label,
                    "max_upload_mb": self.upload_limit_mb(
                        tool.max_upload_mb
                        or settings.max_upload_size_mb
                    ),
                    "max_files": tool.max_files,
                    "notes": tool.notes if available else "",
                    "featured": tool.featured if available else False,
                }
            )
        return tools

    def get(self, tool_id: str) -> Tool | None:
        for tool in self.tools:
            if tool.id == tool_id:
                return tool
        return None

    def is_available(self, tool_id: str) -> bool:
        tool = self.get(tool_id)
        if tool is None:
            return False
        return (
            tool.status == "available"
            and self.driver in tool.environments
        )

    def log_dependency_diagnostics(self) -> None:
        """Log tools made unavailable by missing runtime dependencies.

        Serverless runtimes such as Vercel install a subset of the
        project dependencies, so some tools are reported as unavailable
        without any indication of why. This method emits one WARNING per
        missing dependency, naming the module or binary and every tool it
        affects, so the cause is visible in the deployment logs.
        """
        missing: dict[str, list[str]] = {}
        for tool in self.tools:
            if (
                tool.requires_module
                and not _module_available(tool.requires_module)
            ):
                key = f"module '{tool.requires_module}'"
                missing.setdefault(key, []).append(tool.id)
            if (
                tool.requires_binary
                and not _binary_available(tool.requires_binary)
            ):
                key = f"binary '{tool.requires_binary}'"
                missing.setdefault(key, []).append(tool.id)
        if not missing:
            logger.info("All optional tool dependencies are present.")
            return
        for dependency, tool_ids in missing.items():
            logger.warning(
                "Tool unavailable - missing %s (affects: %s). "
                "Install the dependency to enable it.",
                dependency,
                ", ".join(tool_ids),
            )


capability_registry = CapabilityRegistry()
