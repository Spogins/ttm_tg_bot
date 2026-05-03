"""
Audio transcription service backed by AssemblyAI.
"""
import asyncio
from pathlib import Path

import assemblyai as aai
from loguru import logger

from config.settings import settings

aai.settings.api_key = settings.assemblyai_api_key


def _transcribe_file(path: str) -> str:
    """
    Blocking AssemblyAI call — runs in a thread via asyncio.to_thread.

    :param path: Path to the audio file on disk.
    :return: Transcribed text string (empty string if nothing was recognized).
    """
    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"],  # priority list: best model first, fallback to v2
        language_detection=True,
    )
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    return transcript.text or ""  # returns empty string if speech was detected but no words recognized


async def transcribe(file_path: str) -> str:
    """
    Transcribe the audio file at file_path, raising RuntimeError on timeout or failure.

    :param file_path: Path to the audio file on disk.
    :return: Transcribed text string.
    """
    logger.debug(f"Transcribing {file_path}")
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(_transcribe_file, file_path),  # AssemblyAI SDK is blocking; offload to thread pool
            timeout=60,  # hard 60 s limit to avoid hanging the bot
        )
        logger.debug(f"Transcription result: {text[:80]}")
        return text
    except TimeoutError:
        raise RuntimeError("Транскрипция заняла слишком много времени. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
