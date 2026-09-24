"""robots.txt and sitemap.xml, generated from the tool registry so new
tools are listed without anyone remembering to edit a file."""

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from app.core.capabilities import capability_registry
from app.core.config import settings

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"

router = APIRouter(tags=["SEO"])


def _site() -> str:
    return settings.public_site_url.rstrip("/")


def _lastmod(path: Path) -> str:
    try:
        stamp = path.stat().st_mtime
    except OSError:
        stamp = datetime.now(timezone.utc).timestamp()
    return datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()


def sitemap_entries() -> list[tuple[str, str, str]]:
    """(path, lastmod, priority) for every indexable page."""
    entries = [
        ("/", _lastmod(FRONTEND_DIR / "index.html"), "1.0"),
        ("/tools", _lastmod(FRONTEND_DIR / "pages" / "tools.html"), "0.9"),
        ("/about", _lastmod(FRONTEND_DIR / "pages" / "about.html"), "0.5"),
    ]
    for tool in capability_registry.effective_tools():
        page = FRONTEND_DIR / "pages" / f"{tool['id']}.html"
        if tool["status"] == "available" and page.is_file():
            entries.append((f"/tools/{tool['id']}", _lastmod(page), "0.8"))
    return entries


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap() -> Response:
    site = _site()
    urls = "".join(
        f"  <url><loc>{escape(site + path)}</loc><lastmod>{lastmod}</lastmod>"
        f"<priority>{priority}</priority></url>\n"
        for path, lastmod, priority in sitemap_entries()
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/robots.txt", include_in_schema=False)
async def robots() -> PlainTextResponse:
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /errors/\n"
        f"\nSitemap: {_site()}/sitemap.xml\n"
    )
    return PlainTextResponse(body)
