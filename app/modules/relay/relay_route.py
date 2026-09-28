"""HTTP surface of the relay (see relay_service for the why)."""

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app.core.rate_limit import RELAY_PREFIX
from app.modules.relay.relay_service import relay_service

# Below the point where the host cuts a request, with room for the reply.
MAX_WAIT_SECONDS = 20

router = APIRouter(prefix=RELAY_PREFIX, tags=["Relay"])

SessionId = Path(pattern=r"^[0-9a-f]{32}$")
Wait = Query(0, ge=0, le=MAX_WAIT_SECONDS)


@router.post("/{session_id}/chunk")
async def upload_chunk(
    request: Request,
    session_id: str = SessionId,
    offset: int = Query(ge=0),
    size: int = Query(gt=0),
    content_type: str = Query(alias="type", min_length=1, max_length=300),
):
    staged = await relay_service.stage(
        session_id,
        offset,
        size,
        content_type,
        request.stream(),
    )
    return {"staged": staged, "size": size}


@router.post("/{session_id}/run")
async def run(
    request: Request,
    session_id: str = SessionId,
    path: str = Query(min_length=1, max_length=2000),
    method: str = Query("POST"),
    wait: float = Wait,
):
    """Start the staged request; a body sent here is the whole request."""
    size = int(request.headers.get("content-length") or 0)
    if size:
        await relay_service.stage(
            session_id,
            0,
            size,
            request.headers.get("content-type", "application/octet-stream"),
            request.stream(),
        )
    relay_service.start(session_id, request.app, request, method.upper(), path)
    return await _respond(session_id, wait)


@router.get("/{session_id}")
async def collect(session_id: str = SessionId, wait: float = Wait):
    return await _respond(session_id, wait)


async def _respond(session_id: str, wait: float):
    recorded = await relay_service.collect(session_id, wait)
    if recorded is None:
        return JSONResponse({"status": "running"}, status_code=202)
    headers = dict(recorded["headers"])
    return FileResponse(
        recorded["body"],
        status_code=recorded["status"],
        media_type=headers.pop("content-type", None),
        headers=headers,
    )
