"""Vercel Blob I/O helpers."""

import json

from vercel.blob import (
    BlobNotFoundError,
    delete,
    get,
    list_objects,
    put,
)


def job_prefix(prefix: str, job_id: str) -> str:
    return f"{prefix}/{job_id}"


def blob_path(prefix: str, job_id: str, filename: str) -> str:
    return f"{job_prefix(prefix, job_id)}/{filename}"


def put_blob(blob_path_value: str, data: bytes, access: str) -> None:
    # Job metadata is rewritten on every status change; the SDK rejects
    # writes to an existing pathname unless overwrite is explicit.
    put(blob_path_value, data, access=access, overwrite=True)


def get_blob(blob_path_value: str, access: str) -> bytes | None:
    # Bypass the CDN cache, otherwise polling sees the first version of
    # metadata.json forever.
    try:
        result = get(blob_path_value, access=access, use_cache=False)
    except BlobNotFoundError:
        return None
    return result.content


def decode_metadata(data: bytes | None) -> dict:
    if data is None:
        return {}
    return json.loads(data.decode("utf-8"))


def delete_blob_prefix(prefix: str, job_id: str) -> None:
    base = job_prefix(prefix, job_id)
    blobs = []
    cursor = None
    while True:
        page = list_objects(
            prefix=base,
            cursor=cursor,
            limit=1000,
        )
        blobs.extend(page.blobs)
        if not page.has_more or page.cursor is None:
            break
        cursor = page.cursor
    if blobs:
        delete([blob.pathname for blob in blobs])
