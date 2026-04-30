import asyncio
from pathlib import Path

import assemblyai as aai
from loguru import logger

from config.settings import settings

aai.settings.api_key = settings.assemblyai_api_key


def _transcribe_file(path: str) -> str:
    config = aai.TranscriptionConfig(language_detection=True)
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(path)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    return transcript.text or ""


async def transcribe(file_path: str) -> str:
    logger.debug(f"Transcribing {file_path}")
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(_transcribe_file, file_path),
            timeout=60,
        )
        logger.debug(f"Transcription result: {text[:80]}")
        return text
    except TimeoutError:
        raise RuntimeError("Транскрипция заняла слишком много времени. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
