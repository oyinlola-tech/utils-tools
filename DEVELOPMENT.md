# Development Guide

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
sudo apt install ghostscript   # Debian/Ubuntu; needed for gs-backed tools
./start.sh                     # http://127.0.0.1:8000 (--reload enabled)
```

## Tests

```bash
python -m pytest tests/ -q
```

The suite (110 tests) covers:

- `tests/unit/test_api.py` — unified error format, health, capabilities manifest
- `tests/unit/test_capabilities.py` — registry gating per environment
- `tests/unit/test_image_tools.py` — convert/resize(cover)/metadata/watermark/background replace
- `tests/unit/test_pdf_tools.py` — merge/split/rotate/extract/from-images/page selection
- `tests/unit/test_file_tools.py` — analyze/zip/duplicates
- `tests/unit/test_devtools.py` — favicon/SVG optimizer/QR/barcode
- `tests/unit/test_new_tool_api.py` — endpoint contracts + page/JS serving
- Legacy suites for compression, jobs, storage.

### Browser tests

`tests/browser` runs the frontend in a real browser against a server it
starts itself. They are skipped unless Playwright is installed, and use
the Chromium or Chrome already on the machine (`BROWSER_PATH` overrides
the choice):

```bash
pip install playwright
python -m pytest tests/browser -q
```

Run them after changing anything under `frontend/assets/js/local/` or the
server tools those modules stand in for.

## Adding a new tool

1. **Registry**: add an entry to `app/core/capabilities.py` (id, name,
   environments, limits). Run `test_capabilities.py` — it asserts the count.
2. **Backend**: create or extend the owning module under `app/modules/`
   with `route → controller → service → repository → schema` (mirror
   `app/modules/image/` as the reference). Register the router in
   `app/main.py`.
3. **Storage**: if the tool outputs files, route them through the module
   repository and return a `download_url` using
   `storage.generate_download_url(filename, expiry)`.
4. **Frontend**: create `frontend/pages/{tool_id}.html` and
   `frontend/assets/js/pages/{tool_id}.js` using the shared bootstrap in
   `tool-kit.js`. The page HTML must include the shell elements
   (`#tool-title`, `#tool-description`, `#tool-upload`, `#tool-run`,
   `#tool-result`) — see `frontend/pages/image-converter.html`.
5. **Tests**: add unit tests for the service and endpoint contract tests to
   `test_new_tool_api.py`; the page + JS serving assertion is automatic.
6. **Verify**: `python -m pytest tests/ -q` and `node --check` on the new JS.

## Client-side tools

If a tool needs no backend (cropper, editor, base64 pair, screenshot
beautifier), keep the page script fully self-contained and mark it in the
registry with `"backend": false` so no route is expected.

A tool that has a backend can still be done in the browser when the
browser produces the same result: add it to `TOOLS` in
`frontend/assets/js/local/index.js` and return `null` for whatever it
does not handle. The page script does not change. Add a test to
`tests/browser/test_local_tools.py` that compares it with the endpoint.

## Conventions

- No comments in code unless they explain a non-obvious decision.
- Services raise `ValueError` for bad input; controllers translate to
  `400 INVALID_REQUEST` (or `UNSUPPORTED_FORMAT`).
- Never import `PIL`, `pikepdf`, or `gs` directly in controllers — go
  through adapters.
- Keep all routes under `/api/v1` using `API_PREFIX` from `app/api/__init__.py`.
- Frontend: `node --check` before considering a page script done.

## Environment variables

See `.env.example`. Only `STORAGE_DRIVER` and `BLOB_READ_WRITE_TOKEN` affect
runtime behavior; the rest are tunable limits and paths.
