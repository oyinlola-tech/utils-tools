"""Controller for text & speech tool HTTP operations."""

import logging
from typing import Any, Dict

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.core.exceptions import ProcessingError
from app.modules.text.text_repository import text_repository
from app.modules.text.text_schema import (
    CaseConverterRequest,
    TextDiffRequest,
    TextToSpeechRequest,
    WordCounterRequest,
)
from app.modules.text.text_service import text_service
from app.shared.utils.download_util import download_response

logger = logging.getLogger(__name__)


class TextController:
    def diff(self, request: TextDiffRequest) -> Dict[str, Any]:
        try:
            result = text_service.diff(request.text1, request.text2)
            return {"success": True, "data": result}
        except ProcessingError as err:
            raise HTTPException(status_code=400, detail=str(err))

    def convert_case(self, request: CaseConverterRequest) -> Dict[str, Any]:
        try:
            result = text_service.convert_case(request.text, request.target_case)
            return {"success": True, "result": result}
        except ProcessingError as err:
            raise HTTPException(status_code=400, detail=str(err))

    def count_words(self, request: WordCounterRequest) -> Dict[str, Any]:
        try:
            result = text_service.count_words(request.text)
            return {"success": True, "data": result}
        except ProcessingError as err:
            raise HTTPException(status_code=400, detail=str(err))

    def text_to_speech(self, request: TextToSpeechRequest) -> Dict[str, Any]:
        try:
            temp_path = text_service.text_to_speech(request.text, request.language)
            data = temp_path.read_bytes()
            temp_path.unlink(missing_ok=True)
            # Persist through storage so the download works on any
            # serverless instance, not just the one that generated it.
            output_path = text_repository.save_output_file(data, temp_path.name)
            filename = output_path.name
            return {
                "success": True,
                "filename": filename,
                "size_bytes": len(data),
                "download_url": f"/api/v1/tools/text/download/{filename}",
            }
        except ProcessingError as err:
            raise HTTPException(status_code=400, detail=str(err))

    def serve_file(self, filename: str) -> FileResponse:
        file_path = text_repository.get_output_file(filename)
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found or expired.")
        return download_response(file_path, "audio/mpeg", filename)


text_controller = TextController()
