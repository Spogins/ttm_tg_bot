import asyncio
import os

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import BotCommand
from loguru import logger

from config.logging import setup_logging
from config.settings import settings
from db.mongodb import connect as mongo_connect, disconnect as mongo_disconnect
from db.qdrant import connect as qdrant_connect, disconnect as qdrant_disconnect
from bot.setup import create_bot, create_dispatcher

BOT_COMMANDS = [
    BotCommand(command="start", description="Начать работу"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="projects", description="Список проектов"),
    BotCommand(command="estimate", description="Оценить задачу"),
    BotCommand(command="sprint", description="Оценить задачи спринта"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="cancel", description="Отменить текущее действие"),
]


async def run_polling():
    await mongo_connect()
    await qdrant_connect()

    bot = create_bot()
    dp = create_dispatcher()

    await bot.set_my_commands(BOT_COMMANDS)
    logger.info("Starting in polling mode")
    try:
        await dp.start_polling(bot)
    finally:
        await mongo_disconnect()
        await qdrant_disconnect()
        await bot.session.close()


async def on_startup(bot, dp):
    await mongo_connect()
    await qdrant_connect()
    await bot.set_my_commands(BOT_COMMANDS)
    await bot.set_webhook(f"{settings.webhook_url}{settings.webhook_path}")
    logger.info(f"Webhook set: {settings.webhook_url}{settings.webhook_path}")


async def on_shutdown(bot, dp):
    await mongo_disconnect()
    await qdrant_disconnect()
    await bot.delete_webhook()


def run_webhook():
    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(lambda: on_startup(bot, dp))
    dp.shutdown.register(lambda: on_shutdown(bot, dp))

    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    logger.info("Starting in webhook mode")
    web.run_app(app, host=settings.webapp_host, port=settings.webapp_port)


def main():
    setup_logging(env=os.getenv("ENV", "development"))

    if settings.dev_mode:
        asyncio.run(run_polling())
    else:
        run_webhook()


if __name__ == "__main__":
    main()
