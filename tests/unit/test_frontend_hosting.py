"""The static host's configuration has to match the files it serves."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
CONFIG = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))


def test_preloaded_modules_exist():
    preloaded = [
        path
        for rule in CONFIG["headers"]
        for header in rule["headers"]
        if header["key"] == "Link"
        for path in re.findall(r"</static/([^>]+)>; rel=modulepreload", header["value"])
    ]
    assert preloaded
    missing = [path for path in preloaded if not (FRONTEND / path).is_file()]
    assert missing == []


def test_api_is_preconnected_and_proxied_to_the_same_origin():
    origins = {
        origin
        for rule in CONFIG["headers"]
        for header in rule["headers"]
        if header["key"] == "Link"
        for origin in re.findall(r"<(https://[^>]+)>; rel=preconnect", header["value"])
    }
    proxied = {
        re.match(r"https://[^/]+", rewrite["destination"]).group(0)
        for rewrite in CONFIG["rewrites"]
        if rewrite["destination"].startswith("https://")
    }
    configured = re.findall(
        r'"(https://[^"]+)"',
        (FRONTEND / "assets/js/config.js").read_text(encoding="utf-8"),
    )
    assert origins == proxied == set(configured)


def test_page_rewrites_point_at_real_files():
    for rewrite in CONFIG["rewrites"]:
        destination = rewrite["destination"]
        if destination.startswith("/pages/") and ":" not in destination:
            assert (FRONTEND / destination.lstrip("/")).is_file()
