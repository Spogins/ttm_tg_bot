from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from config.settings import settings
from db.mongodb import users as users_db
from bot.states.states import EstimationStates

# Состояния, в которых происходит LLM-запрос
LLM_STATES = {
    EstimationStates.awaiting_task,
    EstimationStates.clarifying,
}


class UserMiddleware(BaseMiddleware):
    """Загружает или создаёт пользователя и кладёт в data['user']."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not event.from_user:
            return await handler(event, data)

        user = await users_db.get_or_create_user(
            user_id=event.from_user.id,
            first_name=event.from_user.first_name,
            username=event.from_user.username,
        )
        data["user"] = user
        return await handler(event, data)


class TokenLimitMiddleware(BaseMiddleware):
    """Блокирует LLM-запросы при превышении лимита токенов."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        fsm_context: FSMContext = data.get("state")
        if fsm_context is None:
            return await handler(event, data)

        current_state = await fsm_context.get_state()
        if current_state not in {s.state for s in LLM_STATES}:
            return await handler(event, data)

        user_id = event.from_user.id
        allowed, message = await users_db.check_token_limits(
            user_id=user_id,
            daily_limit=settings.daily_token_limit,
            monthly_limit=settings.monthly_token_limit,
        )

        if not allowed:
            logger.info(f"Token limit reached for user {user_id}")
            await event.answer(f"⚠️ {message}")
            return

        return await handler(event, data)
