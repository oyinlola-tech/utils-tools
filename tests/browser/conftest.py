"""Fixtures for tests that run the frontend in a real browser.

Skipped unless Playwright and a Chromium are installed::

    pip install playwright
    python -m pytest tests/browser -q
"""

import base64
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="session")
def site():
    """The application, served the way a visitor reaches it."""
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env={**os.environ, "APP_ENV": "development", "STORAGE_DRIVER": "local"},
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("the application did not start")
        yield url
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    executable = os.environ.get("BROWSER_PATH") or next(
        (path for path in map(shutil.which, BROWSERS) if path),
        None,
    )
    with playwright_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(executable_path=executable, headless=True)
        except playwright_api.Error as error:
            pytest.skip(f"no browser to run: {error}")
        yield launched
        launched.close()


# Runs a local tool, or the server endpoint it replaces, on the same
# files, and hands back the response with its downloads as base64.
_CALL = """async ({path, files, fields, local}) => {
    const entries = files.map((file) => ({
        name: file.field,
        file: new File([Uint8Array.from(atob(file.data), (c) => c.charCodeAt(0))], file.name, {type: file.type}),
    }));
    let result;
    const started = performance.now();
    if (local) {
        const tools = await import('/static/assets/js/local/index.js');
        result = await tools.runLocally(path, entries, fields);
    } else {
        const body = new FormData();
        for (const entry of entries) body.append(entry.name, entry.file);
        for (const [key, value] of Object.entries(fields)) body.append(key, String(value));
        const response = await fetch('/api/v1' + path, {method: 'POST', body});
        result = await response.json();
    }
    const milliseconds = Math.round(performance.now() - started);
    const downloads = {};
    const collect = async (value) => {
        if (!value || typeof value !== 'object') return;
        for (const [key, item] of Object.entries(value)) {
            if (key === 'download_url' && typeof item === 'string') {
                const bytes = new Uint8Array(await (await fetch(item)).arrayBuffer());
                let binary = '';
                for (let at = 0; at < bytes.length; at += 32768) {
                    binary += String.fromCharCode(...bytes.subarray(at, at + 32768));
                }
                downloads[item] = btoa(binary);
            } else {
                await collect(item);
            }
        }
    };
    await collect(result);
    return {result, downloads, milliseconds};
}"""


class Tools:
    def __init__(self, page) -> None:
        self.page = page

    def call(self, path: str, files: list[tuple], fields: dict | None = None, local: bool = True):
        """files: (form field, filename, bytes, content type)."""
        outcome = self.page.evaluate(
            _CALL,
            {
                "path": path,
                "local": local,
                "fields": fields or {},
                "files": [
                    {
                        "field": field,
                        "name": name,
                        "type": content_type,
                        "data": base64.b64encode(data).decode(),
                    }
                    for field, name, data, content_type in files
                ],
            },
        )
        outcome["downloads"] = {
            url: base64.b64decode(data) for url, data in outcome["downloads"].items()
        }
        return outcome

    def local(self, path, files, fields=None):
        return self.call(path, files, fields, local=True)

    def server(self, path, files, fields=None):
        return self.call(path, files, fields, local=False)


@pytest.fixture
def tools(site, browser):
    page = browser.new_page()
    page.goto(f"{site}/about", wait_until="load")
    yield Tools(page)
    page.close()
