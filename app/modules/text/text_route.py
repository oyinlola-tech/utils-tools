"""FastAPI router for Text and Speech API tools."""

import logging

from fastapi import APIRouter, HTTPException

from app.api import API_PREFIX
from app.modules.text.text_controller import text_controller
from app.modules.text.text_schema import (
    CaseConverterRequest,
    TextDiffRequest,
    TextToSpeechRequest,
    WordCounterRequest,
)
from app.shared.utils.file_util import is_safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{API_PREFIX}/tools/text",
    tags=["Text & Audio Tools"],
)


@router.post("/diff")
def text_diff(request: TextDiffRequest):
    return text_controller.diff(request)


@router.post("/convert-case")
async def case_converter(request: CaseConverterRequest):
    return text_controller.convert_case(request)


@router.post("/word-counter")
async def word_counter(request: WordCounterRequest):
    return text_controller.count_words(request)


@router.post("/text-to-speech")
def text_to_speech(request: TextToSpeechRequest):
    return text_controller.text_to_speech(request)


@router.get("/download/{filename}")
def download_speech_file(filename: str):
    if not is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return text_controller.serve_file(filename)
