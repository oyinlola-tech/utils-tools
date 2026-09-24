"""Pydantic schemas for Text & Audio Tools API requests."""

from pydantic import BaseModel, Field


class TextDiffRequest(BaseModel):
    # difflib is quadratic in the worst case; bound the input.
    text1: str = Field(..., max_length=500_000, description="Original text")
    text2: str = Field(..., max_length=500_000, description="Modified text")


class CaseConverterRequest(BaseModel):
    text: str = Field(..., max_length=1_000_000, description="Text to convert")
    target_case: str = Field(
        ...,
        description="Target case (camel, snake, kebab, title, upper, lower)",
    )


class WordCounterRequest(BaseModel):
    text: str = Field(..., max_length=2_000_000, description="Text to analyze")


class TextToSpeechRequest(BaseModel):
    # gTTS issues one HTTP request per ~100 characters.
    text: str = Field(..., max_length=5_000, description="Text input to speak")
    language: str = Field(default="en", description="Language code (e.g., en, es, fr, de)")
