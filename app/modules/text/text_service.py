"""Business logic for text and speech processing tools."""

import difflib
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from app.core.exceptions import ProcessingError
from app.core.logging import get_tool_logger
from app.infrastructure.storage import storage

logger = logging.getLogger(__name__)


def _get_gtts():
    """Import gTTS lazily so the app boots when it is not installed."""
    from gtts import gTTS

    return gTTS


class TextService:
    def diff(self, text1: str, text2: str) -> Dict[str, Any]:
        """Generate line-by-line unified diff between two texts."""
        tool_logger = get_tool_logger("text-diff")
        started = time.monotonic()
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        diff_lines = list(
            difflib.unified_diff(
                lines1,
                lines2,
                fromfile="Original",
                tofile="Modified",
                lineterm="",
            )
        )
        tool_logger.info(
            "diff completed: %d -> %d lines, %d changed, %.2fs",
            len(lines1),
            len(lines2),
            len(diff_lines),
            time.monotonic() - started,
        )
        return {
            "diff": "\n".join(diff_lines),
            "original_lines": len(lines1),
            "modified_lines": len(lines2),
            "has_changes": len(diff_lines) > 0,
        }

    def convert_case(self, text: str, target_case: str) -> str:
        """Convert text into specified case convention."""
        tool_logger = get_tool_logger("case-converter")
        started = time.monotonic()
        if not text:
            return ""

        words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+", text)
        if not words:
            words = text.split()

        case_lower = target_case.lower()
        if case_lower == "camel":
            result = words[0].lower() + "".join(w.capitalize() for w in words[1:])
        elif case_lower == "snake":
            result = "_".join(w.lower() for w in words)
        elif case_lower == "kebab":
            result = "-".join(w.lower() for w in words)
        elif case_lower == "title":
            result = " ".join(w.capitalize() for w in words)
        elif case_lower == "upper":
            result = text.upper()
        elif case_lower == "lower":
            result = text.lower()
        else:
            raise ProcessingError(f"Unsupported target case: {target_case}")

        tool_logger.info(
            "case conversion '%s': %d chars -> %s in %.2fs",
            case_lower,
            len(text),
            case_lower,
            time.monotonic() - started,
        )
        return result

    def count_words(self, text: str) -> Dict[str, Any]:
        """Analyze character, word, sentence, line count, and reading time."""
        tool_logger = get_tool_logger("word-counter")
        started = time.monotonic()
        char_count = len(text)
        char_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", ""))
        words = re.findall(r"\b\w+\b", text)
        word_count = len(words)
        lines = text.splitlines()
        line_count = len(lines) if text else 0
        sentences = re.split(r"[.!?]+", text)
        sentence_count = len([s for s in sentences if s.strip()])
        reading_time_minutes = round(word_count / 200, 1)

        tool_logger.info(
            "counted %d words, %d characters in %.2fs",
            word_count,
            char_count,
            time.monotonic() - started,
        )
        return {
            "characters": char_count,
            "characters_no_spaces": char_no_spaces,
            "words": word_count,
            "sentences": sentence_count,
            "lines": line_count,
            "reading_time_minutes": reading_time_minutes,
        }

    def text_to_speech(self, text: str, language: str = "en") -> Path:
        """Generate MP3 audio file from text using gTTS."""
        tool_logger = get_tool_logger("text-to-speech")
        if not text.strip():
            raise ProcessingError("Text input for speech generation cannot be empty.")

        started = time.monotonic()
        try:
            gTTS = _get_gtts()
            tts = gTTS(text=text, lang=language, slow=False)
            # storage.temp_path is writable on every driver (/tmp on
            # Vercel); settings.temp_directory is read-only there.
            download_dir = Path(storage.temp_path)
            download_dir.mkdir(parents=True, exist_ok=True)
            job_id = uuid.uuid4().hex[:8]
            output_file = download_dir / f"speech_{job_id}.mp3"
            tts.save(str(output_file))
            try:
                output_size = output_file.stat().st_size
            except FileNotFoundError:
                output_size = 0
            tool_logger.info(
                "speech generated: %s (%d bytes, %d chars) in %.2fs",
                output_file.name,
                output_size,
                len(text),
                time.monotonic() - started,
            )
            return output_file
        except Exception as err:
            tool_logger.error("Error generating text-to-speech: %s", str(err))
            raise ProcessingError(f"Failed to generate speech audio: {err}")


text_service = TextService()
