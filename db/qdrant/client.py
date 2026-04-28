from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from loguru import logger

from config.settings import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    if _client is None:
        raise RuntimeError("Qdrant client is not initialized. Call connect() first.")
    return _client


async def connect() -> None:
    global _client
    _client = AsyncQdrantClient(
        url=f"https://{settings.qdrant_host}",
        api_key=settings.qdrant_api_key or None,
    )
    await _client.get_collections()
    logger.info("Qdrant connected")


async def disconnect() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("Qdrant disconnected")


async def ensure_collection(name: str, vector_size: int, distance: Distance = Distance.COSINE) -> None:
    client = get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if name not in existing:
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )
        logger.info(f"Qdrant collection '{name}' created")
    else:
        logger.debug(f"Qdrant collection '{name}' already exists")
