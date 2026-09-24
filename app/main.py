import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import API_PREFIX
from app.core.capabilities import capability_registry
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
    StaticCacheMiddleware,
    schedule_cleanup_sweep,
)
from app.modules.background.background_route import (
    router as background_router,
)
from app.modules.capabilities.capability_route import (
    router as capability_router,
)
from app.modules.compression.compression_route import (
    image_router,
)
from app.modules.compression.compression_route import (
    router as compression_router,
)
from app.modules.devtools.dev_tools_route import (
    router as dev_tools_router,
)
from app.modules.file_tools.file_tool_route import (
    router as file_tool_router,
)
from app.modules.image.image_tools_route import (
    images_router,
)
from app.modules.image.image_tools_route import (
    router as image_tools_router,
)
from app.modules.jobs.job_route import router as job_router
from app.modules.pdf.pdf_route import router as pdf_router
from app.modules.seo.seo_route import (
    router as seo_router,
)
from app.modules.text.text_route import router as text_router
from app.modules.video.video_route import router as video_router

setup_logging()

if settings.storage_driver == "vercel" and not settings.blob_read_write_token:
    raise ValueError(
        "BLOB_READ_WRITE_TOKEN is required when STORAGE_DRIVER=vercel."
    )

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
app = FastAPI(
    title=settings.app_name,
    description=(
        "Utils-tool - local-first file and media utility application"
    ),
    version=settings.app_version,
)
from app.core.exceptions import register_exception_handlers

register_exception_handlers(app)

app.add_middleware(
    RequestIDMiddleware,
)
app.add_middleware(
    StaticCacheMiddleware,
)
app.add_middleware(
    RateLimitMiddleware,
)
app.add_middleware(
    BodySizeLimitMiddleware,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)
app.include_router(background_router)
app.include_router(compression_router)
app.include_router(image_router)
app.include_router(job_router)
app.include_router(capability_router)
app.include_router(image_tools_router)
app.include_router(images_router)
app.include_router(pdf_router)
app.include_router(file_tool_router)
app.include_router(dev_tools_router)
app.include_router(video_router)
app.include_router(text_router)
app.include_router(seo_router)

@app.on_event("startup")
async def startup_cleanup():
    # Sweep in the background so a cold start is not delayed by it.
    schedule_cleanup_sweep()
    capability_registry.log_dependency_diagnostics()
@app.get("/")
async def home():
    return FileResponse(
        FRONTEND_DIR / "index.html",
    )


_TOOL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@app.get("/about")
async def about_page():
    return FileResponse(FRONTEND_DIR / "pages" / "about.html")


@app.get("/tools")
async def tools_page():
    return FileResponse(FRONTEND_DIR / "pages" / "tools.html")


@app.get("/tools/{tool_id}")
async def tool_page(tool_id: str):
    if not _TOOL_ID_PATTERN.match(tool_id):
        raise HTTPException(
            status_code=404,
            detail="Tool page not found.",
        )
    page_path = (
        FRONTEND_DIR / "pages" / f"{tool_id}.html"
    )
    if not page_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Tool page not found.",
        )
    return FileResponse(page_path)


_ERROR_PAGE_NAME_PATTERN = re.compile(r"^[a-z0-9-]+(?:\.html)?$")


@app.get("/errors/{name}")
async def error_page(name: str):
    """Serve the designed error pages at their canonical path.

    Both ``/errors/404`` and ``/errors/404.html`` work. Numeric names
    respond with the matching HTTP status code so browsers treat them
    as real errors rather than plain pages.
    """
    if not _ERROR_PAGE_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=404,
            detail="Error page not found.",
        )
    stem = name[:-5] if name.endswith(".html") else name
    page_path = FRONTEND_DIR / "errors" / f"{stem}.html"
    if not page_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Error page not found.",
        )
    status_code = int(stem) if stem.isdigit() else 200
    return FileResponse(
        page_path,
        status_code=status_code,
        media_type="text/html",
    )


@app.get(f"{API_PREFIX}/health")
async def health_check():
    return {
        "status": "ok",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "storage_driver": settings.storage_driver,
    }
