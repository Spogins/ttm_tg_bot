from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.mongo import MongoStorage

from config.settings import settings
from db.mongodb import get_database
from bot.handlers import common, projects, estimation
from bot.middlewares.voice import VoiceTranscriptionMiddleware
from bot.middlewares.token_limit import UserMiddleware, TokenLimitMiddleware


def create_bot() -> Bot:
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    db = get_database()
    storage = MongoStorage(db.client, db_name=settings.mongodb_db_name)
    dp = Dispatcher(storage=storage)

    dp.message.middleware(UserMiddleware())
    dp.message.middleware(TokenLimitMiddleware())
    dp.message.middleware(VoiceTranscriptionMiddleware())

    dp.include_router(common.router)
    dp.include_router(projects.router)
    dp.include_router(estimation.router)

    return dp
