import asyncio
import os

from config.logging import setup_logging
from config.settings import settings
from db.mongodb import connect as mongo_connect, disconnect as mongo_disconnect
from db.qdrant import connect as qdrant_connect, disconnect as qdrant_disconnect


async def main():
    setup_logging(env=os.getenv("ENV", "development"))

    await mongo_connect()
    await qdrant_connect()

    # TODO: запустить бота


if __name__ == "__main__":
    asyncio.run(main())
