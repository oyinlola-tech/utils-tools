from pathlib import Path
from uuid import uuid4

from app.shared.constants.file_constants import (
    MAX_FILENAME_LENGTH,
)


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def get_file_stem(filename: str) -> str:
    return Path(filename).stem


def generate_file_id() -> str:
    return uuid4().hex


def generate_filename(
    original_filename: str,
    extension: str | None = None,
) -> str:
    file_id = generate_file_id()
    original_stem = get_file_stem(original_filename)
    safe_stem = "".join(
        character
        for character in original_stem
        if character.isalnum()
        or character in ("-", "_")
    )
    if not safe_stem:
        safe_stem = "file"
    if extension:
        extension = extension.lstrip(".")
    else:
        extension = get_file_extension(
            original_filename
        ).lstrip(".")
    filename = f"{safe_stem}_{file_id}.{extension}"
    if len(filename) > MAX_FILENAME_LENGTH:
        max_stem = MAX_FILENAME_LENGTH - len(extension) - len(file_id) - 2
        safe_stem = safe_stem[:max_stem]
        filename = f"{safe_stem}_{file_id}.{extension}"
    return filename


def unique_filename(filename: str) -> str:
    """Keep the readable name but make it unguessable and collision-free.

    Outputs share one directory (and one Blob namespace on Vercel), so two
    users uploading ``image.png`` would otherwise overwrite and download
    each other's results.
    """
    if not is_safe_filename(filename):
        raise ValueError("Invalid filename")
    path = Path(filename)
    token = generate_file_id()[:12]
    max_stem = MAX_FILENAME_LENGTH - len(path.suffix) - len(token) - 1
    return f"{path.stem[:max_stem]}_{token}{path.suffix}"


def is_safe_filename(filename: str) -> bool:
    if not filename or filename in {".", ".."}:
        return False
    path = Path(filename)
    if path.is_absolute() or path.name != filename:
        return False
    return not any(part in {"", ".", ".."} for part in path.parts)


def resolve_safe_path(base_directory: Path, filename: str) -> Path:
    if not is_safe_filename(filename):
        raise ValueError("Invalid filename")
    base_path = base_directory.resolve()
    output_path = (base_path / filename).resolve()
    output_path.relative_to(base_path)
    return output_path
