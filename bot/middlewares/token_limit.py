"""
Middlewares for user hydration and per-user LLM token-limit enforcement.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger

from config.settings import settings
from db.mongodb import users as users_db
from bot.states.states import EstimationStates

# states that trigger an LLM call; token usage is only checked for these
LLM_STATES = {
    EstimationStates.awaiting_task,
    EstimationStates.clarifying,
}


class UserMiddleware(BaseMiddleware):
    """
    Load or create the User document from MongoDB and inject it into data['user'].
    Messages without a sender (e.g. channel posts) are passed through unchanged.
    """

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
    """
    Block LLM requests and notify the user when their daily or monthly token limit is exceeded.
    Only active for states listed in LLM_STATES; all other states are passed through.
    """

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
        # aiogram stores state as a string ("Group:state"); compare against .state attribute, not State objects
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
