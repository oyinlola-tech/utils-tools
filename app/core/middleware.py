"""Request ID, rate-limit and static-cache middleware.

Every request receives a short random ID that is attached to log
records and returned in the ``X-Request-ID`` header, so errors can be
traced without leaking internals.

The rate limiter protects the API from being overwhelmed by bursts of
requests, returning a designed 429 page for browsers and the standard
error envelope for API clients.

The static-cache middleware forces browsers and the edge cache to
revalidate static assets, so a fresh deploy is never masked by stale
JS/CSS.
"""

import asyncio
import logging
import time
import uuid
from collections import deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import API_PREFIX
from app.core.config import settings
from app.core.exceptions import _error_page_response

logger = logging.getLogger(__name__)

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
_MAX_TRACKED_CLIENTS = 5000
_UNLIMITED_METHODS = {"GET", "HEAD", "OPTIONS"}


def _evict_idle_buckets(now: float, window: float) -> None:
    """Drop clients with no requests in the current window.

    Buckets were never removed, so the dict grew by one entry per
    distinct client IP for the life of the process.
    """
    for key in [
        key
        for key, bucket in _RATE_LIMIT_BUCKETS.items()
        if not bucket or now - bucket[-1] > window
    ]:
        del _RATE_LIMIT_BUCKETS[key]


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
    """In-memory sliding-window limiter for API requests.

    One window per client IP. Limits are best-effort on serverless
    runtimes (state is per instance) but are enough to absorb accidental
    bursts and abusive loops.
    """

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(API_PREFIX):
            return await call_next(request)
        if settings.app_env != "production":
            return await call_next(request)
        if request.method in _UNLIMITED_METHODS:
            # Job polling (every 500 ms) and downloads are cheap reads;
            # counting them made a single long compression job exhaust
            # the 120 req/min budget and fail with 429s mid-job.
            return await call_next(request)

        client = self._client_key(request)
        now = time.monotonic()
        window = float(settings.rate_limit_window_seconds)
        limit = settings.rate_limit_max_requests

        if len(_RATE_LIMIT_BUCKETS) > _MAX_TRACKED_CLIENTS:
            _evict_idle_buckets(now, window)
        bucket = _RATE_LIMIT_BUCKETS.setdefault(client, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            response = _error_page_response(
                request,
                429,
                "RATE_LIMITED",
                "Too many requests. Please try again in a moment.",
            )
            response.headers["Retry-After"] = str(int(window))
            return response

        bucket.append(now)
        return await call_next(request)

    @staticmethod
    def _client_key(request: Request) -> str:
        # Set by Vercel's edge and not client-controllable, unlike the
        # first X-Forwarded-For entry.
        for header in ("x-vercel-forwarded-for", "x-real-ip"):
            value = request.headers.get(header, "").strip()
            if value:
                return value.split(",")[0].strip()
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        host = request.client.host if request.client else "unknown"
        return host


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
