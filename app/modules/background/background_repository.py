from pathlib import Path

from app.infrastructure.storage import storage
from app.shared.utils.file_util import resolve_safe_path, unique_filename


class BackgroundRepository:
    def save_processed_file(
        self,
        data: bytes,
        filename: str,
    ) -> Path:
        output_path = resolve_safe_path(
            storage.processed_path,
            unique_filename(filename),
        )
        storage.write(output_path, data)
        return output_path

    def get_processed_file(
        self,
        filename: str,
    ) -> Path:
        return storage.materialize(
            resolve_safe_path(
                storage.processed_path,
                filename,
            )
        )

    def get_file_size(
        self,
        file_path: Path,
    ) -> int:
        return storage.get_size(file_path)


background_repository = BackgroundRepository()
