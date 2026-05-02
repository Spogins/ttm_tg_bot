"""
Bot and dispatcher factory functions.
"""
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.mongo import MongoStorage

from config.settings import settings
from db.mongodb import get_database
from bot.handlers import common, projects, estimation
from bot.middlewares.voice import VoiceTranscriptionMiddleware
from bot.middlewares.token_limit import UserMiddleware, TokenLimitMiddleware


def create_bot() -> Bot:
    """
    Instantiate the Telegram Bot with the configured token.

    :return: Configured Bot instance.
    """
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    """
    Create Dispatcher with MongoDB FSM storage, middlewares, and all routers registered.

    :return: Fully configured Dispatcher instance.
    """
    db = get_database()
    # uses MongoStorage so FSM state survives bot restarts
    storage = MongoStorage(db.client, db_name=settings.mongodb_db_name)
    dp = Dispatcher(storage=storage)

    dp.message.middleware(UserMiddleware())
    dp.message.middleware(TokenLimitMiddleware())
    dp.message.middleware(VoiceTranscriptionMiddleware())

    dp.include_router(common.router)
    dp.include_router(projects.router)
    dp.include_router(estimation.router)

    return dp
