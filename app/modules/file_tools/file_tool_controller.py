from fastapi import HTTPException, UploadFile

from app.modules.file_tools.file_tool_repository import (
    file_tool_repository,
)
from app.modules.file_tools.file_tool_schema import (
    DuplicateReport,
    FileAnalysisResponse,
    FileToolResponse,
)
from app.modules.file_tools.file_tool_service import (
    file_tools_service,
)


class FileToolsController:
    async def _read_files(
        self,
        files: list[UploadFile],
    ) -> list[tuple[str, bytes]]:
        if not files:
            raise HTTPException(
                status_code=400,
                detail="No files were provided.",
            )
        sources: list[tuple[str, bytes]] = []
        for file in files:
            if not file.filename:
                raise HTTPException(
                    status_code=400,
                    detail="Filename is required",
                )
            file_data = await file.read()
            if not file_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file is empty: {file.filename}",
                )
            sources.append((file.filename, file_data))
        return sources

    def _save(
        self,
        data: bytes,
        filename: str,
        details: dict | None = None,
    ) -> FileToolResponse:
        output_path = file_tool_repository.save_output_file(
            data,
            filename,
        )
        return FileToolResponse(
            success=True,
            filename=output_path.name,
            size_bytes=len(data),
            download_url=f"/api/v1/tools/file/download/{output_path.name}",
            details=details or {},
        )

    async def analyze(
        self,
        files: list[UploadFile],
    ) -> FileAnalysisResponse:
        sources = await self._read_files(files)
        results = file_tools_service.analyze(sources)
        return FileAnalysisResponse(
            success=True,
            files=results,
        )

    async def create_zip(
        self,
        files: list[UploadFile],
    ) -> FileToolResponse:
        sources = await self._read_files(files)
        try:
            data = file_tools_service.create_zip(sources)
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to create archive: {error}",
            ) from error
        first_name = sources[0][0]
        base_name = first_name.rsplit(".", 1)[0]
        # _save() already makes the name unique; generate_filename()
        # here added a second 32-char token to every archive name.
        return self._save(
            data,
            f"{base_name}-archive.zip",
            {"file_count": len(sources)},
        )

    async def find_duplicates(
        self,
        files: list[UploadFile],
    ) -> list[DuplicateReport]:
        sources = await self._read_files(files)
        return [
            DuplicateReport(**report)
            for report in file_tools_service.find_duplicates(
                sources
            )
        ]


file_tools_controller = FileToolsController()
