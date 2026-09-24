from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.shared.utils.file_util import is_safe_filename


def _dedupe(name: str, used: set[str]) -> str:
    """Give repeated entry names a " (n)" suffix.

    Two uploads called ``image.png`` produced duplicate ZIP entries, and
    extracting the archive silently kept only one of them.
    """
    candidate = name
    stem, dot, suffix = name.rpartition(".")
    if not dot:
        stem, suffix = name, ""
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter}){dot}{suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


class ZipAdapter:
    def create_archive(
        self,
        files: list[tuple[str, bytes]],
    ) -> bytes:
        archive_buffer = BytesIO()
        with ZipFile(
            archive_buffer,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            used: set[str] = set()
            for filename, file_data in files:
                # Windows clients may send backslash-separated paths.
                safe_name = Path(filename.replace("\\", "/")).name
                if not is_safe_filename(safe_name):
                    raise ValueError(
                        f"Invalid archive entry: {filename}"
                    )
                safe_name = _dedupe(safe_name, used)
                archive.writestr(
                    safe_name,
                    file_data,
                )
        return archive_buffer.getvalue()

    def create_archive_from_directory(
        self,
        source_directory: Path,
        output_path: Path,
    ) -> Path:
        source_directory = source_directory.resolve()
        with ZipFile(
            output_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for file_path in sorted(
                source_directory.rglob("*")
            ):
                if not file_path.is_file():
                    continue
                real_path = file_path.resolve()
                if not str(real_path).startswith(
                    str(source_directory) + "/"
                ) and real_path != source_directory:
                    continue
                arcname = real_path.relative_to(
                    source_directory
                )
                archive.write(
                    real_path,
                    arcname=arcname.as_posix(),
                )
        return output_path


zip_adapter = ZipAdapter()
