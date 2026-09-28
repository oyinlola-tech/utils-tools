"""Run an API request detached from the connection that asked for it.

Some hosts cut any HTTP request that lasts longer than a fixed time
(about 30 seconds on the cPanel server), however large the upload or
slow the tool. The relay keeps every request short:

1. the client uploads the request body in chunks, each a quick request;
2. the staged request is replayed against the application in a worker
   thread, through the full middleware stack, as if it had arrived
   normally;
3. the client collects the recorded response, waiting or polling.

Everything is kept on disk so any worker process can serve any step.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.api import API_PREFIX
from app.core.config import settings
from app.core.exceptions import (
    AppException,
    InvalidRequestError,
    NotFoundError,
)
from app.core.rate_limit import RELAY_PREFIX

logger = logging.getLogger(__name__)

MAX_CHUNK_BYTES = 16 * 1024 * 1024
HEARTBEAT_SECONDS = 5
# No heartbeat for this long means the worker running the request died.
STALLED_AFTER_SECONDS = 45
_POLL_SECONDS = 0.1
_READ_BLOCK_BYTES = 1024 * 1024
_SESSION_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_FORWARDED_HEADERS = (
    "host",
    "user-agent",
    "accept-language",
    "x-forwarded-for",
    "x-real-ip",
    "x-vercel-forwarded-for",
)
_REPLAYED_HEADERS = ("content-type", "content-disposition", "retry-after")


class RelayConflictError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, 409, "RELAY_CONFLICT")


class RelayNotStartedError(AppException):
    """Tells a client that lost its run request to send it again."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 404, "RELAY_NOT_STARTED")


class RelayInterruptedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            "Processing was interrupted. Please try again.",
            500,
            "PROCESSING_INTERRUPTED",
        )


class _Session:
    def __init__(self, root: Path, session_id: str) -> None:
        if not _SESSION_PATTERN.match(session_id):
            raise InvalidRequestError("Invalid relay session.")
        self.id = session_id
        self.directory = root / session_id
        self.meta = self.directory / "meta.json"
        self.body = self.directory / "body"
        self.parts = self.directory / "parts"
        self.state = self.directory / "state.json"
        self.heartbeat = self.directory / "heartbeat"
        self.response_meta = self.directory / "response.json"
        self.response_body = self.directory / "response.body"


class RelayService:
    @property
    def enabled(self) -> bool:
        # Blob-backed deployments have no disk shared between instances.
        return settings.storage_driver == "local"

    @property
    def root(self) -> Path:
        return Path(settings.temp_path) / "relay"

    def session(self, session_id: str) -> _Session:
        if not self.enabled:
            raise NotFoundError("The relay is not available on this deployment.")
        return _Session(self.root, session_id)

    # ------------------------------------------------------------ staging

    async def stage(
        self,
        session_id: str,
        offset: int,
        size: int,
        content_type: str,
        stream,
    ) -> int:
        """Write one chunk of the request body. Returns bytes staged so far."""
        session = self.session(session_id)
        limit = settings.max_request_body_mb * 1024 * 1024
        if size > limit:
            raise AppException(
                f"Request is too large. The maximum upload size is "
                f"{settings.max_request_body_mb} MB.",
                413,
                "FILE_TOO_LARGE",
            )
        if offset >= size:
            raise InvalidRequestError("Chunk starts beyond the end of the upload.")
        self._open(session, size, content_type)

        written = 0
        descriptor = os.open(session.body, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            async for block in stream:
                if not block:
                    continue
                if written + len(block) > MAX_CHUNK_BYTES or offset + written + len(block) > size:
                    raise InvalidRequestError("Chunk is larger than declared.")
                os.pwrite(descriptor, block, offset + written)
                written += len(block)
        finally:
            os.close(descriptor)
        if not written:
            raise InvalidRequestError("Chunk is empty.")
        # The marker is what makes the chunk count; a chunk cut short by a
        # dropped connection never gets one and is simply sent again.
        (session.parts / f"{offset}-{written}").touch()
        return self._staged_bytes(session)

    def _open(self, session: _Session, size: int, content_type: str) -> None:
        if session.state.exists():
            raise RelayConflictError("This request has already been started.")
        session.parts.mkdir(parents=True, exist_ok=True)
        meta = {"size": size, "content_type": content_type}
        # Linked into place so parallel chunks never read a half-written file.
        temporary = session.directory / f"meta.{os.getpid()}.{threading.get_ident()}"
        temporary.write_text(json.dumps(meta), encoding="utf-8")
        try:
            os.link(temporary, session.meta)
        except FileExistsError:
            if self._read_json(session.meta) != meta:
                raise RelayConflictError(
                    "Chunk does not match the upload it belongs to."
                ) from None
        finally:
            temporary.unlink(missing_ok=True)

    def _staged_bytes(self, session: _Session) -> int:
        """Bytes covered from the start of the body without a gap."""
        covered = 0
        try:
            entries = list(session.parts.iterdir())
        except FileNotFoundError:
            return 0
        for start, length in sorted(
            tuple(int(value) for value in entry.name.split("-"))
            for entry in entries
        ):
            if start > covered:
                break
            covered = max(covered, start + length)
        return covered

    # ---------------------------------------------------------- execution

    def started(self, session_id: str) -> bool:
        return self.session(session_id).state.exists()

    def start(self, session_id: str, app, request, method: str, target: str) -> None:
        """Replay the staged request in the background. Idempotent."""
        session = self.session(session_id)
        path, query = self._validate_target(method, target)
        if session.state.exists():
            return  # a retry of a run request that did get through
        meta = self._read_json(session.meta)
        if meta is None:
            raise RelayNotStartedError("Nothing has been uploaded for this request.")
        if self._staged_bytes(session) < meta["size"]:
            raise RelayConflictError("The upload is incomplete.")
        try:
            with open(session.state, "x", encoding="utf-8") as handle:
                json.dump({"target": target, "started": time.time()}, handle)
        except FileExistsError:
            return

        headers = [
            (name.encode("latin-1"), request.headers[name].encode("latin-1"))
            for name in (*_FORWARDED_HEADERS, settings.trusted_proxy_header.lower())
            if name and name in request.headers
        ]
        headers += [
            (b"accept", b"application/json"),
            (b"content-type", meta["content_type"].encode("latin-1")),
            (b"content-length", str(meta["size"]).encode("ascii")),
        ]
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": request.url.scheme,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query.encode("utf-8"),
            "root_path": "",
            "headers": headers,
            "client": request.scope.get("client"),
            "server": request.scope.get("server"),
            "extensions": {},
        }
        session.heartbeat.touch()
        threading.Thread(
            target=self._run,
            args=(session, app, scope, meta["size"]),
            name=f"relay-{session.id[:8]}",
            daemon=True,
        ).start()

    @staticmethod
    def _validate_target(method: str, target: str) -> tuple[str, str]:
        parts = urlsplit(target)
        path = parts.path
        if (
            method != "POST"
            or parts.scheme
            or parts.netloc
            or ".." in path
            or not path.startswith(f"{API_PREFIX}/")
            or path.startswith(RELAY_PREFIX)
        ):
            raise InvalidRequestError("This request cannot be relayed.")
        return path, parts.query

    def _run(self, session: _Session, app, scope: dict, size: int) -> None:
        # A thread with its own event loop: tools do their CPU work inside
        # async handlers, which would otherwise freeze the worker's loop
        # and with it every request the worker is serving.
        stop = threading.Event()
        threading.Thread(
            target=self._beat,
            args=(session, stop),
            name=f"relay-beat-{session.id[:8]}",
            daemon=True,
        ).start()
        started = time.monotonic()
        try:
            status = asyncio.run(self._replay(session, app, scope, size))
            logger.info(
                "Relayed %s %s -> %s in %.1fs (%d byte body)",
                scope["method"],
                scope["path"],
                status,
                time.monotonic() - started,
                size,
            )
        except Exception:
            logger.exception("Relayed request %s failed", scope["path"])
            self._record(
                session,
                500,
                {"content-type": "application/json"},
                json.dumps(
                    {
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": "An unexpected error occurred. Please try again.",
                            "request_id": session.id[:16],
                            "status": 500,
                        }
                    }
                ).encode("utf-8"),
            )
        finally:
            stop.set()
            session.body.unlink(missing_ok=True)
            shutil.rmtree(session.parts, ignore_errors=True)

    @staticmethod
    def _beat(session: _Session, stop: threading.Event) -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                session.heartbeat.touch()
            except OSError:
                return

    async def _replay(self, session: _Session, app, scope: dict, size: int) -> int:
        finished = asyncio.Event()
        response: dict = {}

        with open(session.body, "rb") as body, open(
            f"{session.response_body}.part", "wb"
        ) as recorded:

            async def receive() -> dict:
                if body.tell() < size:
                    block = body.read(_READ_BLOCK_BYTES)
                    return {
                        "type": "http.request",
                        "body": block,
                        "more_body": body.tell() < size,
                    }
                # Only report a disconnect once the response is complete,
                # or handlers watching for one would abort mid-response.
                await finished.wait()
                return {"type": "http.disconnect"}

            async def send(message: dict) -> None:
                if message["type"] == "http.response.start":
                    response["status"] = message["status"]
                    response["headers"] = {
                        name.decode("latin-1").lower(): value.decode("latin-1")
                        for name, value in message.get("headers", [])
                    }
                elif message["type"] == "http.response.body":
                    recorded.write(message.get("body", b""))
                    if not message.get("more_body"):
                        finished.set()

            await app(scope, receive, send)

        if "status" not in response:
            raise RuntimeError("The application returned no response.")
        os.replace(f"{session.response_body}.part", session.response_body)
        self._record(session, response["status"], response["headers"])
        return response["status"]

    @staticmethod
    def _record(
        session: _Session,
        status: int,
        headers: dict,
        body: bytes | None = None,
    ) -> None:
        if body is not None:
            session.response_body.write_bytes(body)
        kept = {name: headers[name] for name in _REPLAYED_HEADERS if name in headers}
        temporary = session.response_meta.with_suffix(".part")
        temporary.write_text(
            json.dumps({"status": status, "headers": kept}),
            encoding="utf-8",
        )
        # Renamed last: its presence is what announces a finished request.
        os.replace(temporary, session.response_meta)

    # --------------------------------------------------------- collection

    async def collect(self, session_id: str, wait_seconds: float) -> dict | None:
        """Return the recorded response, or None while it is still running."""
        session = self.session(session_id)
        deadline = time.monotonic() + wait_seconds
        while True:
            recorded = self._read_json(session.response_meta)
            if recorded is not None:
                return {**recorded, "body": session.response_body}
            if not session.state.exists():
                raise RelayNotStartedError("This request has not been started.")
            try:
                idle = time.time() - session.heartbeat.stat().st_mtime
            except OSError:
                idle = 0.0
            if idle > STALLED_AFTER_SECONDS:
                raise RelayInterruptedError()
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(_POLL_SECONDS)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None


relay_service = RelayService()
