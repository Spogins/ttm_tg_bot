from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger

from config.settings import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized. Call connect() first.")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db_name]


async def connect() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    await _client.admin.command("ping")
    logger.info("MongoDB connected")
    await _ensure_indexes()


async def disconnect() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB disconnected")


async def _ensure_indexes() -> None:
    db = get_database()
    await db["users"].create_index("user_id", unique=True)
    await db["projects"].create_index("project_id", unique=True)
    logger.info("MongoDB indexes ensured")
