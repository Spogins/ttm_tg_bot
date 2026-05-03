# -*- coding: utf-8 -*-
"""
Middleware that transparently transcribes voice messages before they reach handlers.
"""
import tempfile
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import ContentType, Message
from loguru import logger

from services.transcription import transcribe


class VoiceTranscriptionMiddleware(BaseMiddleware):
    """Download and transcribe voice messages, replacing event.text with the result.

    Non-voice messages are passed through unchanged.
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """
        Intercept voice messages, transcribe them, and inject the transcript as event.text.

        :param handler: The next handler in the middleware chain.
        :param event: The incoming Telegram message.
        :param data: Shared handler data dict (contains 'bot').
        :return: Result of the next handler, or None if transcription fails.
        """
        if event.content_type != ContentType.VOICE:
            return await handler(event, data)

        bot = data["bot"]
        voice = event.voice

        await event.answer("🎙 Распознаю голосовое сообщение...")

        try:
            file = await bot.get_file(voice.file_id)
            # delete=False keeps the file after the context manager exits so transcribe() can read it
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                await bot.download_file(file.file_path, destination=tmp.name)
                tmp_path = tmp.name  # capture path before the context manager closes the handle

            text = await transcribe(tmp_path)

            if not text:
                await event.answer("Не удалось распознать речь. Попробуйте ещё раз.")
                return

            # aiogram Message is a frozen Pydantic model; bypass normal assignment to inject the transcript
            object.__setattr__(event, "text", text)
            logger.info(f"Voice transcribed for user {event.from_user.id}: {text[:60]}")

        except RuntimeError as e:
            await event.answer(str(e))
            return
        except Exception as e:
            logger.error(f"Voice middleware error: {e}")
            await event.answer("Ошибка при распознавании. Попробуйте текстом.")
            return

        return await handler(event, data)
