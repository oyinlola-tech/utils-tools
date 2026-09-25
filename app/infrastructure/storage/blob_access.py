"""Vercel Blob access mode, learned from the store instead of trusted blindly.

A store is created either public or private, and every ``put``/``get``
must use the matching mode. When ``BLOB_ACCESS_MODE`` disagrees with the
store, Blob rejects every write ("Cannot use public access on a private
store") and every tool fails. Instead, the first rejection switches this
process to the store's real mode and the call is retried.
"""

import logging
import re

from vercel.blob import BlobError, get, put

from app.core.config import settings

logger = logging.getLogger(__name__)

_MISMATCH = re.compile(r"access on an? (public|private) store", re.IGNORECASE)

_mode = settings.blob_access_mode


def access_mode() -> str:
    return _mode


def _adopt_store_mode(error: Exception) -> bool:
    """Switch to the store's mode if ``error`` is an access mismatch."""
    global _mode
    match = _MISMATCH.search(str(error))
    if not match:
        return False
    store_mode = match.group(1).lower()
    if store_mode == _mode:
        return False
    logger.warning(
        "BLOB_ACCESS_MODE=%s does not match the Blob store, which is %s; "
        "using %s. Set BLOB_ACCESS_MODE=%s to silence this warning.",
        _mode,
        store_mode,
        store_mode,
        store_mode,
    )
    _mode = store_mode
    return True


def put_blob(path: str, data: bytes, **kwargs):
    try:
        return put(path, data, access=_mode, **kwargs)
    except BlobError as error:
        if _adopt_store_mode(error):
            return put(path, data, access=_mode, **kwargs)
        raise


def get_blob(path: str, **kwargs):
    try:
        return get(path, access=_mode, **kwargs)
    except BlobError as error:
        if _adopt_store_mode(error):
            return get(path, access=_mode, **kwargs)
        raise
