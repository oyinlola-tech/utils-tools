"""The Blob access mode must follow the store, not a stale env var."""

import types

import pytest
from vercel.blob import BlobError, BlobNotFoundError

from app.infrastructure.storage import blob_access


@pytest.fixture
def private_store(monkeypatch):
    calls = []

    def fake(kind):
        def op(path, *args, access, **kwargs):
            calls.append((kind, access))
            if access != "private":
                raise BlobError(
                    "Vercel Blob: Cannot use public access on a private store. "
                    "The store is configured with private access."
                )
            return types.SimpleNamespace(url=f"https://x/{path}", content=b"ok")
        return op

    monkeypatch.setattr(blob_access, "put", fake("put"))
    monkeypatch.setattr(blob_access, "get", fake("get"))
    monkeypatch.setattr(blob_access, "_mode", "public")
    return calls


def test_put_adopts_private_store_mode_and_retries(private_store):
    blob_access.put_blob("processed/a.webp", b"data", overwrite=True)
    assert private_store == [("put", "public"), ("put", "private")]
    assert blob_access.access_mode() == "private"

    # Later calls use the learned mode straight away.
    blob_access.get_blob("processed/a.webp", use_cache=False)
    assert private_store[-1] == ("get", "private")
    assert len(private_store) == 3


def test_other_blob_errors_are_not_swallowed(monkeypatch):
    def missing(path, *args, access, **kwargs):
        raise BlobNotFoundError()

    monkeypatch.setattr(blob_access, "get", missing)
    monkeypatch.setattr(blob_access, "_mode", "public")
    with pytest.raises(BlobNotFoundError):
        blob_access.get_blob("nope")
    assert blob_access.access_mode() == "public"


def test_private_store_downloads_are_never_redirected(monkeypatch, tmp_path):
    from app.shared.utils import download_util

    monkeypatch.setattr(blob_access, "_mode", "private")
    assert download_util._blob_download_url(tmp_path / "x.png") == ""
