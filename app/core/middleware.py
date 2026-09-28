"""Request ID, rate-limit and static-cache middleware.

Every request receives a short random ID that is attached to log
records and returned in the ``X-Request-ID`` header, so errors can be
traced without leaking internals.

The rate limiter covers every endpoint (see ``app.core.rate_limit``),
returning a designed 429 page for browsers and the standard error
envelope for API clients.

The static-cache middleware forces browsers and the edge cache to
revalidate static assets, so a fresh deploy is never masked by stale
JS/CSS.
"""

import asyncio
import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import API_PREFIX
from app.core.config import settings
from app.core.exceptions import _error_page_response
from app.core.rate_limit import client_key, rate_limiter, rules_for

logger = logging.getLogger(__name__)

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def schedule_cleanup_sweep() -> None:
    """Run the TTL sweep off the event loop, at most once per interval.

    Request-triggered rather than a timer so it also runs on stateless
    serverless instances that never see a long-lived process.
    """
    from app.modules.jobs.job_cleanup_service import job_cleanup_service

    if not job_cleanup_service.claim_sweep():
        return
    task = asyncio.get_running_loop().create_task(
        asyncio.to_thread(job_cleanup_service.run_claimed_sweep)
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id or len(request_id) > 64:
            request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith(API_PREFIX):
            try:
                schedule_cleanup_sweep()
            except Exception:
                logger.exception("Could not schedule cleanup sweep")
        return response


class StaticCacheMiddleware(BaseHTTPMiddleware):
    """Make static assets revalidate so deploys always reach users.

    FastAPI's StaticFiles mount sends no Cache-Control header, so
    browsers and the Vercel edge cache can serve outdated JS/CSS
    indefinitely after a deploy. ``no-cache`` lets the browser keep the
    file locally but forces a revalidation with the origin on every
    request.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Charge every request to its client's budget, or answer 429."""

    async def dispatch(self, request: Request, call_next):
        if settings.app_env != "production":
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)

        tier, rules = rules_for(request.method, request.url.path)
        retry_after = rate_limiter.check(
            client_key(
                request.client.host if request.client else None,
                request.headers,
            ),
            tier,
            rules,
        )
        if retry_after is not None:
            response = _error_page_response(
                request,
                429,
                "RATE_LIMITED",
                "Too many requests. Please try again in a moment.",
            )
            response.headers["Retry-After"] = str(retry_after)
            return response
        return await call_next(request)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before they are buffered.

    Upload handlers call ``await file.read()`` and only then compare the
    size against per-tool limits, so a multi-GB upload was spooled to
    disk and then read fully into memory. This pure-ASGI middleware
    checks ``Content-Length`` up front and counts streamed bytes for
    chunked requests.
    """

    def __init__(self, app, max_bytes: int | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def _limit(self) -> int:
        return self.max_bytes or settings.max_request_body_mb * 1024 * 1024

    async def _reject(self, scope, receive, send) -> None:
        from starlette.requests import Request as StarletteRequest

        limit_mb = self._limit() // (1024 * 1024)
        response = _error_page_response(
            StarletteRequest(scope, receive),
            413,
            "FILE_TOO_LARGE",
            f"Request is too large. The maximum upload size is {limit_mb} MB.",
        )
        await response(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self._limit()
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(scope, receive, send)
