"""Local job metadata persistence."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.infrastructure.jobs.local_paths import (
    get_metadata_path,
)


def create_job_metadata(root_path: Path, job_id: str | None = None) -> tuple[str, dict]:
    job_id = job_id or uuid4().hex
    metadata = {
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "created",
    }
    write_metadata(root_path, job_id, metadata)
    return job_id, metadata


def write_metadata(
    root_path: Path,
    job_id: str,
    metadata: dict,
) -> None:
    metadata_path = get_metadata_path(root_path, job_id)
    # Write-then-rename so a concurrent poll never reads a half-written
    # (empty) file while the background task updates status.
    temp_path = metadata_path.with_name(f"{metadata_path.name}.{uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, metadata_path)


def read_metadata(
    root_path: Path,
    job_id: str,
) -> dict:
    metadata_path = get_metadata_path(root_path, job_id)
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))
