"""
Async Qdrant client singleton with collection management helpers.
"""
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from loguru import logger

from config.settings import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    """
    Return the active Qdrant client, raising if connect() was not called.

    :return: The initialized AsyncQdrantClient instance.
    """
    if _client is None:
        raise RuntimeError("Qdrant client is not initialized. Call connect() first.")
    return _client


async def connect() -> None:
    """
    Initialize the Qdrant client and verify connectivity.

    :return: None
    """
    global _client
    _client = AsyncQdrantClient(
        url=f"https://{settings.qdrant_host}",
        api_key=settings.qdrant_api_key or None,  # empty string → None so the client skips auth headers
    )
    await _client.get_collections()  # lightweight call to confirm connectivity
    logger.info("Qdrant connected")


async def disconnect() -> None:
    """
    Close the Qdrant connection and reset the singleton.

    :return: None
    """
    global _client  # module-level singleton
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("Qdrant disconnected")


async def ensure_collection(name: str, vector_size: int, distance: Distance = Distance.COSINE) -> None:
    """
    Create the Qdrant collection if it does not already exist.

    :param name: Collection name.
    :param vector_size: Dimensionality of the embedding vectors.
    :param distance: Distance metric to use (default: cosine).
    :return: None
    """
    client = get_client()
    existing = {c.name for c in (await client.get_collections()).collections}  # set for O(1) membership check
    if name not in existing:
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )
        logger.info(f"Qdrant collection '{name}' created")
    else:
        logger.debug(f"Qdrant collection '{name}' already exists")
