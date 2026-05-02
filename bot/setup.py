# -*- coding: utf-8 -*-
"""
Bot and dispatcher factory functions.
"""
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.mongo import MongoStorage

from bot.handlers import common, estimation, projects
from bot.middlewares.token_limit import TokenLimitMiddleware, UserMiddleware
from bot.middlewares.voice import VoiceTranscriptionMiddleware
from config.settings import settings
from db.mongodb import get_database


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

    # order matters: user hydration → token check → transcription
    dp.message.middleware(UserMiddleware())
    dp.message.middleware(TokenLimitMiddleware())
    dp.message.middleware(VoiceTranscriptionMiddleware())  # runs last, after token gate

    dp.include_router(common.router)
    dp.include_router(projects.router)
    dp.include_router(estimation.router)

    return dp
