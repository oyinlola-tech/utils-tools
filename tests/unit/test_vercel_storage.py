"""Tests for the Vercel Blob storage adapters.

The official ``vercel.blob`` SDK is mocked out — these tests verify the
adapter's behaviour (key mapping, local mirror, error translation)
without touching a real Blob store or needing a token.
"""

import json

import pytest

from app.infrastructure.jobs.vercel_job_storage import VercelJobStorage
from app.infrastructure.storage.vercel_storage import VercelStorage


class FakeResult:
    """Minimal stand-in for SDK result objects."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture()
def fake_sdk(monkeypatch):
    """Expose the SDK functions used by the adapters as controllable mocks."""
    calls = {"put": [], "get": [], "delete": [], "head": [], "list": []}

    blob_store = {}

    def fake_put(path, body, **kwargs):
        calls["put"].append((path, body, kwargs))
        blob_store[path] = body
        return FakeResult(
            url=f"https://store.public.blob.vercel-storage.com/{path}",
            pathname=path,
        )

    def fake_get(url_or_path, **kwargs):
        calls["get"].append((url_or_path, kwargs))
        if url_or_path not in blob_store:
            from vercel.blob import BlobNotFoundError

            raise BlobNotFoundError()
        return FakeResult(content=blob_store[url_or_path], url=f"https://x/{url_or_path}")

    def fake_delete(urls, **kwargs):
        calls["delete"].append((urls, kwargs))
        for url in urls if isinstance(urls, list) else [urls]:
            blob_store.pop(url, None)

    def fake_head(url_or_path, **kwargs):
        calls["head"].append((url_or_path, kwargs))
        if url_or_path not in blob_store:
            from vercel.blob import BlobNotFoundError

            raise BlobNotFoundError()
        return FakeResult(size=len(blob_store[url_or_path]), url=f"https://x/{url_or_path}")

    module = "app.infrastructure.storage.vercel_storage"
    monkeypatch.setattr(f"{module}.delete", fake_delete)
    monkeypatch.setattr(f"{module}.head", fake_head)

    # Reads and writes go through blob_access, which picks the store's mode.
    access_module = "app.infrastructure.storage.blob_access"
    monkeypatch.setattr(f"{access_module}.put", fake_put)
    monkeypatch.setattr(f"{access_module}.get", fake_get)
    monkeypatch.setattr(f"{access_module}._mode", "public")

    jobs_module = "app.infrastructure.jobs.vercel_blob_io"
    monkeypatch.setattr(f"{jobs_module}.delete", fake_delete)

    def fake_list_objects(**kwargs):
        prefix = kwargs.get("prefix", "")
        matching_blobs = []
        for pathname in blob_store:
            if pathname.startswith(prefix):
                matching_blobs.append(
                    FakeResult(pathname=pathname)
                )
        return FakeResult(blobs=matching_blobs, has_more=False, cursor=None)

    monkeypatch.setattr(f"{jobs_module}.list_objects", fake_list_objects)

    return calls, blob_store


@pytest.fixture()
def vercel_storage(fake_sdk, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.core.config.settings.blob_read_write_token",
        "test-token",
    )
    # Point the adapter's local root at pytest's temp dir so blob keys
    # (``uploads/...`` etc.) map exactly like they do in production.
    monkeypatch.setattr(
        "app.infrastructure.storage.vercel_storage._LOCAL_ROOT",
        tmp_path,
    )
    storage = VercelStorage()
    storage.upload_path = tmp_path / "uploads"
    storage.processed_path = tmp_path / "processed"
    storage.compressed_path = tmp_path / "compressed"
    storage.temp_path = tmp_path / "temp"
    return storage


class TestVercelStorage:
    def test_write_roundtrips_to_blob(self, vercel_storage, fake_sdk):
        calls, blob_store = fake_sdk
        target = vercel_storage.upload_path / "a.png"
        vercel_storage.write(target, b"png-bytes")
        assert target.read_bytes() == b"png-bytes"
        assert "uploads/a.png" in blob_store
        assert blob_store["uploads/a.png"] == b"png-bytes"
        assert calls["put"][0][2]["access"] == "public"

    def test_write_creates_parent_directories(self, vercel_storage, fake_sdk):
        target = vercel_storage.upload_path / "deep" / "nested" / "f.bin"
        vercel_storage.write(target, b"data")
        assert target.is_file()

    def test_read_pulls_from_blob(self, vercel_storage, fake_sdk):
        _, blob_store = fake_sdk
        blob_store["processed/out.png"] = b"result"
        data = vercel_storage.read(vercel_storage.processed_path / "out.png")
        assert data == b"result"

    def test_materialize_writes_local_copy(self, vercel_storage, fake_sdk):
        _, blob_store = fake_sdk
        blob_store["processed/out.png"] = b"result"
        path = vercel_storage.materialize(vercel_storage.processed_path / "out.png")
        assert path.is_file()
        assert path.read_bytes() == b"result"

    def test_materialize_missing_returns_path_without_error(self, vercel_storage):
        path = vercel_storage.materialize(vercel_storage.processed_path / "missing.png")
        assert not path.exists()

    def test_exists_uses_head(self, vercel_storage, fake_sdk):
        _, blob_store = fake_sdk
        blob_store["uploads/x.bin"] = b"x"
        assert vercel_storage.exists(vercel_storage.upload_path / "x.bin")
        assert not vercel_storage.exists(vercel_storage.upload_path / "nope.bin")

    def test_get_size(self, vercel_storage, fake_sdk):
        _, blob_store = fake_sdk
        blob_store["uploads/x.bin"] = b"12345"
        assert vercel_storage.get_size(vercel_storage.upload_path / "x.bin") == 5

    def test_delete_removes_blob_and_local(self, vercel_storage, fake_sdk):
        calls, blob_store = fake_sdk
        target = vercel_storage.upload_path / "gone.bin"
        vercel_storage.write(target, b"bye")
        assert "uploads/gone.bin" in blob_store
        vercel_storage.delete(target)
        assert "uploads/gone.bin" not in blob_store
        assert not target.exists()
        assert calls["delete"]

    def test_delete_missing_is_idempotent(self, vercel_storage):
        vercel_storage.delete(vercel_storage.upload_path / "never.bin")

    def test_get_url_returns_public_url(self, vercel_storage, fake_sdk):
        _, blob_store = fake_sdk
        blob_store["uploads/a.png"] = b"x"
        url = vercel_storage.get_url(vercel_storage.upload_path / "a.png")
        assert "uploads/a.png" in url

    def test_get_url_private_has_no_browser_url(self, fake_sdk, monkeypatch, tmp_path):
        # Private blobs need the server token, so there is no URL a browser
        # can open; downloads are streamed through the app instead.
        monkeypatch.setattr(
            "app.core.config.settings.blob_read_write_token",
            "test-token",
        )
        monkeypatch.setattr(
            "app.infrastructure.storage.blob_access._mode",
            "private",
        )
        monkeypatch.setattr(
            "app.infrastructure.storage.vercel_storage._LOCAL_ROOT",
            tmp_path,
        )
        storage = VercelStorage()
        storage.upload_path = tmp_path / "uploads"
        _, blob_store = fake_sdk
        blob_store["uploads/a.png"] = b"x"
        assert storage.get_url(storage.upload_path / "a.png") == ""

    def test_missing_token_raises(self, fake_sdk, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.blob_read_write_token",
            "",
        )
        storage = VercelStorage()
        with pytest.raises(RuntimeError, match="BLOB_READ_WRITE_TOKEN"):
            storage.write(storage.upload_path / "x.bin", b"data")


class TestVercelJobStorage:
    @pytest.fixture()
    def job_storage(self, fake_sdk, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "app.core.config.settings.blob_read_write_token",
            "test-token",
        )
        monkeypatch.setattr(
            "app.infrastructure.jobs.vercel_job_storage._LOCAL_ROOT",
            tmp_path,
        )
        storage = VercelJobStorage()
        storage.root_path = tmp_path / "jobs"
        storage.download_path = tmp_path / "downloads"
        return storage

    def test_create_job_writes_metadata(self, job_storage, fake_sdk):
        _, blob_store = fake_sdk
        job_id = job_storage.create_job()
        key = f"jobs/{job_id}/metadata.json"
        assert key in blob_store
        metadata = json.loads(blob_store[key].decode("utf-8"))
        assert metadata["status"] == "created"

    def test_write_and_read_metadata_roundtrip(self, job_storage, fake_sdk):
        job_storage.write_metadata("abc", {"status": "running", "job_id": "abc"})
        metadata = job_storage.read_metadata("abc")
        assert metadata["status"] == "running"

    def test_read_missing_metadata_returns_empty(self, job_storage):
        assert job_storage.read_metadata("missing") == {}

    def test_save_input_and_output(self, job_storage, fake_sdk):
        _, blob_store = fake_sdk
        job_storage.save_input("abc", "in.bin", b"input")
        job_storage.save_output("abc", "out.bin", b"output")
        assert blob_store["jobs/abc/input/in.bin"] == b"input"
        assert blob_store["jobs/abc/output/out.bin"] == b"output"

    def test_save_and_materialize_download(self, job_storage, fake_sdk):
        job_storage.save_download("result.zip", b"zip-bytes")
        path = job_storage.materialize_download("result.zip")
        assert path.read_bytes() == b"zip-bytes"

    def test_materialize_missing_download_returns_path(self, job_storage):
        path = job_storage.materialize_download("never.zip")
        assert not path.exists()

    def test_move_download(self, job_storage, fake_sdk):
        source = job_storage.download_path / "tmp.zip"
        source.write_bytes(b"payload")
        dest = job_storage.move_download(source, "final.zip")
        assert dest.read_bytes() == b"payload"

    def test_delete_job_removes_local(self, job_storage, fake_sdk):
        calls, blob_store = fake_sdk
        job_id = job_storage.create_job()
        assert job_storage.get_job_path(job_id).exists()
        metadata_key = f"jobs/{job_id}/metadata.json"
        assert metadata_key in blob_store
        job_storage.delete_job(job_id)
        assert not job_storage.get_job_path(job_id).exists()
        assert metadata_key not in blob_store
        assert calls["delete"]

    def test_constructor_requires_token(self, fake_sdk, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.blob_read_write_token",
            "",
        )
        with pytest.raises(ValueError, match="BLOB_READ_WRITE_TOKEN"):
            VercelJobStorage()
