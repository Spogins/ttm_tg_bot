"""
Async MongoDB client singleton with connection lifecycle and index setup.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger

from config.settings import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """
    Return the active Motor client, raising if connect() was not called.

    :return: The initialized AsyncIOMotorClient instance.
    """
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized. Call connect() first.")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """
    Return the configured application database.

    :return: AsyncIOMotorDatabase for the configured db name.
    """
    return get_client()[settings.mongodb_db_name]


async def connect() -> None:
    """
    Create the Motor client, verify connectivity, and ensure indexes.

    :return: None
    """
    global _client  # module-level singleton
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    await _client.admin.command("ping")  # validates the connection before first use
    logger.info("MongoDB connected")
    await _ensure_indexes()


async def disconnect() -> None:
    """
    Close the Motor client and reset the singleton.

    :return: None
    """
    global _client  # module-level singleton
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB disconnected")


async def _ensure_indexes() -> None:
    """
    Create required unique indexes on users and projects collections.

    :return: None
    """
    db = get_database()
    await db["users"].create_index("user_id", unique=True)
    await db["projects"].create_index("project_id", unique=True)
    logger.info("MongoDB indexes ensured")
