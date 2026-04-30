import tempfile
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, ContentType
from loguru import logger

from services.transcription import transcribe


class VoiceTranscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.content_type != ContentType.VOICE:
            return await handler(event, data)

        bot = data["bot"]
        voice = event.voice

        await event.answer("🎙 Распознаю голосовое сообщение...")

        try:
            file = await bot.get_file(voice.file_id)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                await bot.download_file(file.file_path, destination=tmp.name)
                tmp_path = tmp.name

            text = await transcribe(tmp_path)

            if not text:
                await event.answer("Не удалось распознать речь. Попробуйте ещё раз.")
                return

            # подменяем текст сообщения чтобы хендлеры работали прозрачно
            event.text = text
            logger.info(f"Voice transcribed for user {event.from_user.id}: {text[:60]}")

        except RuntimeError as e:
            await event.answer(str(e))
            return
        except Exception as e:
            logger.error(f"Voice middleware error: {e}")
            await event.answer("Ошибка при распознавании. Попробуйте текстом.")
            return

        return await handler(event, data)
