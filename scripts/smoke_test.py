"""Smoke test for a running deployment: one real request per server tool.

    python scripts/smoke_test.py https://tools.telente.site
    python scripts/smoke_test.py http://127.0.0.1:8000 --only pdf

Every check posts generated sample files, then follows any download link
in the response, so a tool only passes when its output can be fetched.
Tools that run entirely in the browser are not covered here.
"""

import argparse
import io
import sys
import time

import pikepdf
import requests
from PIL import Image

API = "/api/v1"
JOB_TIMEOUT_SECONDS = 120
VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

SAMPLE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
SAMPLE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100.000" height="100.000">'
    b"<!-- comment --><rect x=\"10.12345\" y=\"10.98765\" width=\"50\" "
    b'height="50" fill="#ff0000"/></svg>'
)


def png(width=320, height=240, color=(40, 120, 200)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    for x in range(0, width, 16):
        for y in range(0, height, 16):
            image.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, 90))
    # A centered block gives the background tools a subject to keep.
    image.paste((230, 60, 60), (width // 4, height // 4, width * 3 // 4, height * 3 // 4))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 180, 40)).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def pdf(pages=3) -> bytes:
    document = pikepdf.new()
    for _ in range(pages):
        document.add_blank_page(page_size=(595, 842))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class Deployment:
    def __init__(self, base_url: str, origin: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if origin:
            self.session.headers["Origin"] = origin

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if path.startswith(API):
            return self.base_url + path
        return self.base_url + API + path

    def get(self, path: str) -> requests.Response:
        return self.session.get(self.url(path), timeout=120)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.session.post(self.url(path), timeout=180, **kwargs)

    def wait_for_job(self, job_id: str) -> dict:
        deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            job = self.get(f"/jobs/{job_id}").json()
            if job.get("status") in {"completed", "failed", "cancelled"}:
                return job
            time.sleep(1)
        raise AssertionError(f"job {job_id} did not finish in {JOB_TIMEOUT_SECONDS}s")


def download_links(value) -> list[str]:
    if isinstance(value, dict):
        links = []
        for key, item in value.items():
            if key.endswith("url") and isinstance(item, str) and item.startswith("/"):
                links.append(item)
            else:
                links.extend(download_links(item))
        return links
    if isinstance(value, list):
        return [link for item in value for link in download_links(item)]
    return []


def verify(deployment: Deployment, response: requests.Response) -> str:
    """Assert the response succeeded and its output is retrievable."""
    if response.status_code != 200:
        raise AssertionError(f"HTTP {response.status_code}: {response.text[:200]}")
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type:
        if not response.content:
            raise AssertionError("empty file response")
        return f"{content_type}, {len(response.content)} bytes"
    body = response.json()
    if isinstance(body, dict) and body.get("job_id") and "status" in body:
        body = deployment.wait_for_job(body["job_id"])
        if body.get("status") != "completed":
            raise AssertionError(f"job ended as {body.get('status')}: {str(body)[:200]}")
    links = download_links(body)
    for link in links[:3]:
        downloaded = deployment.get(link)
        if downloaded.status_code != 200 or not downloaded.content:
            raise AssertionError(f"download {link} -> HTTP {downloaded.status_code}")
    return f"ok, {len(links)} download(s)"


def upload(path, files, **fields):
    def run(deployment: Deployment) -> requests.Response:
        return deployment.post(path, files=files(), data=fields)

    return run


def post_json(path, **payload):
    def run(deployment: Deployment) -> requests.Response:
        return deployment.post(path, json=payload)

    return run


def post_form(path, **fields):
    def run(deployment: Deployment) -> requests.Response:
        return deployment.post(path, data=fields)

    return run


def one(name, data, content_type, field="file"):
    return lambda: [(field, (name, data(), content_type))]


def many(field, *parts):
    return lambda: [(field, (name, data(), kind)) for name, data, kind in parts]


IMAGE = ("photo.png", png, "image/png")
PHOTO = ("photo.jpg", jpeg, "image/jpeg")
DOCUMENT = ("document.pdf", pdf, "application/pdf")

CHECKS = [
    ("background-remover", "image", upload("/background/start", one(*IMAGE))),
    (
        "background-replacement",
        "image",
        upload("/background/replace", one(*IMAGE), color="#00ff00"),
    ),
    ("image-compressor", "image", upload("/images/compress", many("files", IMAGE, PHOTO))),
    (
        "image-converter",
        "image",
        upload("/images/convert", many("files", IMAGE), output_format="webp"),
    ),
    (
        "image-resizer",
        "image",
        upload("/images/resize", many("files", IMAGE), resize_mode="aspect", width="160"),
    ),
    (
        "image-cropper",
        "image",
        upload("/tools/image/crop", one(*IMAGE), crop_width="100", crop_height="80"),
    ),
    ("metadata-remover", "image", upload("/tools/image/remove-metadata", one(*PHOTO))),
    ("watermark", "image", upload("/tools/image/watermark", one(*IMAGE), text="Sample")),
    ("palette-extractor", "image", upload("/tools/image/palette-extractor", one(*IMAGE))),
    (
        "social-media-resizer",
        "image",
        upload("/tools/image/resize", one(*IMAGE), width="200", height="200", cover="true"),
    ),
    (
        "pdf-compressor",
        "pdf",
        upload("/compression/batch/start", many("files", DOCUMENT)),
    ),
    ("pdf-merger", "pdf", upload("/tools/pdf/merge", many("files", DOCUMENT, DOCUMENT))),
    ("pdf-splitter", "pdf", upload("/tools/pdf/split", one(*DOCUMENT))),
    ("pdf-to-image", "pdf", upload("/tools/pdf/to-images", one(*DOCUMENT), dpi="72")),
    ("image-to-pdf", "pdf", upload("/tools/pdf/from-images", many("files", IMAGE, PHOTO))),
    ("pdf-rotator", "pdf", upload("/tools/pdf/rotate", one(*DOCUMENT), angle="90")),
    ("pdf-extractor", "pdf", upload("/tools/pdf/extract", one(*DOCUMENT), pages="1-2")),
    ("pdf-encrypt", "pdf", upload("/tools/pdf/encrypt", one(*DOCUMENT), password="s3cret")),
    ("pdf-page-number", "pdf", upload("/tools/pdf/page-number", one(*DOCUMENT))),
    ("pdf-watermark", "pdf", upload("/tools/pdf/watermark", one(*DOCUMENT), text="DRAFT")),
    ("file-analyzer", "file", upload("/tools/file/analyze", many("files", IMAGE, DOCUMENT))),
    ("zip-creator", "file", upload("/tools/file/zip", many("files", IMAGE, DOCUMENT))),
    ("duplicate-finder", "file", upload("/tools/file/duplicates", many("files", IMAGE, IMAGE))),
    (
        "favicon-generator",
        "developer",
        upload("/tools/dev/favicon", one(*IMAGE, field="image"), size="64"),
    ),
    (
        "svg-optimizer",
        "developer",
        upload("/tools/dev/svg-optimize", one("icon.svg", lambda: SAMPLE_SVG, "image/svg+xml")),
    ),
    (
        "svg-generator",
        "developer",
        upload("/tools/dev/svg-generate", one(*IMAGE, field="image")),
    ),
    ("qr-generator", "developer", post_form("/tools/dev/qr", content="https://example.com")),
    ("barcode-generator", "developer", post_form("/tools/dev/barcode", content="123456789012")),
    (
        "json-csv-converter",
        "developer",
        post_json("/tools/dev/json-to-csv", data='[{"a": 1, "b": 2}, {"a": 3, "b": 4}]'),
    ),
    ("json-csv-converter (csv)", "developer", post_json("/tools/dev/csv-to-json", data="a,b\n1,2")),
    ("json-formatter", "developer", post_json("/tools/dev/json-format", json_text='{"a":1}')),
    ("jwt-decoder", "developer", post_json("/tools/dev/jwt-decode", token=SAMPLE_JWT)),
    ("text-diff", "text", post_json("/tools/text/diff", text1="one\ntwo", text2="one\n2")),
    (
        "case-converter",
        "text",
        post_json("/tools/text/convert-case", text="hello world", target_case="upper"),
    ),
    ("word-counter", "text", post_json("/tools/text/word-counter", text="one two three")),
    (
        "text-to-speech",
        "text",
        post_json("/tools/text/text-to-speech", text="Hello from the smoke test."),
    ),
    ("video-downloader (info)", "utility", post_json("/tools/video/info", url=VIDEO_URL)),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url")
    parser.add_argument("--origin", help="send this Origin header, to exercise CORS")
    parser.add_argument("--only", help="run checks whose name or category contains this")
    args = parser.parse_args()

    deployment = Deployment(args.base_url, args.origin)
    failures = 0
    for name, category, run in CHECKS:
        if args.only and args.only not in name and args.only != category:
            continue
        started = time.monotonic()
        try:
            detail = verify(deployment, run(deployment))
            status = "PASS"
        except Exception as error:  # noqa: BLE001 - report and keep going
            detail = f"{type(error).__name__}: {error}"
            status = "FAIL"
            failures += 1
        elapsed = time.monotonic() - started
        print(f"{status}  {name:<28} {elapsed:5.1f}s  {detail}")
    print(f"\n{failures} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
