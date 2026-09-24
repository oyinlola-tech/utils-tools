"""Unified error format and exception handling.

Every API error is returned as::

    {
        "error": {
            "code": "FILE_TOO_LARGE",
            "message": "human readable message",
            "request_id": "abc123...",
            "status": 413
        }
    }

Responses never expose stack traces, filesystem paths, secrets,
environment variables, or internal tokens.
"""

import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import API_PREFIX

logger = logging.getLogger(__name__)

ERROR_PAGES_DIR = (
    Path(__file__).resolve().parents[2] / "frontend" / "errors"
)


def _wants_html(request: Request) -> bool:
    """A browser navigation wants an HTML page; API calls want JSON.

    Browsers send ``Accept: text/html,...`` on navigation, but some
    clients (and simple requests) send ``*/*`` or nothing at all.
    Anything that is not an API path is treated as a page request so
    the designed ``.html`` error pages are always served.
    """
    if request.url.path.startswith(API_PREFIX):
        return False
    accept = request.headers.get("accept", "").lower()
    if not accept or accept.strip() == "*/*":
        return True
    return "text/html" in accept


def _error_page_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
):
    """Return the designed error page for browsers, JSON for the API."""
    if _wants_html(request):
        page = ERROR_PAGES_DIR / f"{status_code}.html"
        if page.is_file():
            return HTMLResponse(
                page.read_text(encoding="utf-8"),
                status_code=status_code,
            )
    return JSONResponse(
        status_code=status_code,
        content=_error_payload(
            request,
            code,
            message,
            status_code,
        ),
    )


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(self.message)


class FileTooLargeError(AppException):
    def __init__(
        self,
        message: str = "File is too large.",
        code: str = "FILE_TOO_LARGE",
    ):
        super().__init__(
            message,
            status.HTTP_413_CONTENT_TOO_LARGE,
            code,
        )


class UnsupportedFileTypeError(AppException):
    def __init__(
        self,
        message: str = "Unsupported file type.",
        code: str = "UNSUPPORTED_FILE_TYPE",
    ):
        super().__init__(
            message,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code,
        )


class ProcessingError(AppException):
    def __init__(
        self,
        message: str = "Processing failed.",
        code: str = "PROCESSING_FAILED",
    ):
        super().__init__(
            message,
            status.HTTP_400_BAD_REQUEST,
            code,
        )


class NotFoundError(AppException):
    def __init__(
        self,
        message: str = "Resource not found.",
        code: str = "NOT_FOUND",
    ):
        super().__init__(
            message,
            status.HTTP_404_NOT_FOUND,
            code,
        )


class InvalidRequestError(AppException):
    def __init__(
        self,
        message: str = "Invalid request.",
        code: str = "INVALID_REQUEST",
    ):
        super().__init__(
            message,
            status.HTTP_400_BAD_REQUEST,
            code,
        )


def _error_payload(
    request: Request,
    code: str,
    message: str,
    status_code: int,
) -> dict:
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = uuid.uuid4().hex
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "status": status_code,
        }
    }


def register_exception_handlers(app) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ):
        return _error_page_response(
            request,
            exc.status_code,
            exc.code,
            exc.message,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        code_map = {
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_400_BAD_REQUEST: "INVALID_REQUEST",
            status.HTTP_413_CONTENT_TOO_LARGE: "FILE_TOO_LARGE",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: (
                "UNSUPPORTED_FILE_TYPE"
            ),
        }
        code = code_map.get(exc.status_code, "REQUEST_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_page_response(
            request,
            exc.status_code,
            code,
            message,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        message = "Invalid request parameters."
        try:
            first = exc.errors()[0]
            field = ".".join(
                str(part) for part in first.get("loc", [])
            )
            message = (
                f"Invalid value for '{field}': "
                f"{first.get('msg', 'validation error')}"
            )
        except (IndexError, KeyError, TypeError):
            pass
        return _error_page_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            message,
        )

    _register_library_error_handlers(app)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ):
        logger.exception(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
        )
        return _error_page_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again.",
        )


def _register_library_error_handlers(app) -> None:
    """Map well-known third-party input errors to 4xx responses.

    These are raised by Pillow/pikepdf on bad user input and are not
    ``ValueError`` subclasses, so tool controllers that only catch
    ``ValueError``/``OSError`` let them through as 500s. This is a
    safety net; controllers should still validate up front.
    """
    from PIL import Image, UnidentifiedImageError

    from app.shared.utils.image_util import ImageTooLargeError

    async def image_too_large(request: Request, exc: Exception):
        message = (
            str(exc)
            if isinstance(exc, ImageTooLargeError)
            else "Image dimensions are too large to process."
        )
        return _error_page_response(
            request,
            status.HTTP_413_CONTENT_TOO_LARGE,
            "FILE_TOO_LARGE",
            message,
        )

    async def bad_image(request: Request, exc: Exception):
        return _error_page_response(
            request,
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "The uploaded file is not a valid image.",
        )

    app.add_exception_handler(ImageTooLargeError, image_too_large)
    app.add_exception_handler(Image.DecompressionBombError, image_too_large)
    app.add_exception_handler(UnidentifiedImageError, bad_image)

    try:
        import pikepdf
    except ImportError:  # pragma: no cover - optional dependency
        return

    async def pdf_password(request: Request, exc: Exception):
        return _error_page_response(
            request,
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "This PDF is password-protected. Remove the password and try again.",
        )

    async def pdf_damaged(request: Request, exc: Exception):
        return _error_page_response(
            request,
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REQUEST",
            "The PDF is damaged or is not a valid PDF.",
        )

    app.add_exception_handler(pikepdf.PasswordError, pdf_password)
    app.add_exception_handler(pikepdf.PdfError, pdf_damaged)
