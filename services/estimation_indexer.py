from openai import AsyncOpenAI
from qdrant_client.models import PointStruct, Distance
from loguru import logger

from config.settings import settings
from db.mongodb.models import Estimation
from db.qdrant.client import ensure_collection, get_client

EMBEDDING_DIM = 1536
COLLECTION_PREFIX = "estimations"

_openai = AsyncOpenAI(api_key=settings.openai_api_key)


def _collection(user_id: int) -> str:
    return f"{COLLECTION_PREFIX}_{user_id}"


async def _embed(text: str) -> list[float]:
    response = await _openai.embeddings.create(
        model=settings.embedding_model,
        input=[text],
    )
    return response.data[0].embedding


def _estimation_text(estimation: Estimation) -> str:
    return (
        f"Task: {estimation.task}\n"
        f"Tech: {', '.join(estimation.tech_stack)}\n"
        f"Project: {estimation.project_name}\n"
        f"Hours: {estimation.total_hours}, Complexity: {estimation.complexity}"
    )


async def index_estimation(estimation: Estimation) -> None:
    collection = _collection(estimation.user_id)
    await ensure_collection(collection, vector_size=EMBEDDING_DIM, distance=Distance.COSINE)

    text = _estimation_text(estimation)
    vector = await _embed(text)

    point = PointStruct(
        id=abs(hash(estimation.estimation_id)) % (2 ** 63),
        vector=vector,
        payload={
            "task": estimation.task,
            "total_hours": estimation.total_hours,
            "tech_stack": estimation.tech_stack,
            "project_name": estimation.project_name,
            "complexity": estimation.complexity,
            "estimation_id": estimation.estimation_id,
        },
    )

    client = get_client()
    await client.upsert(collection_name=collection, points=[point])
    logger.info(f"Indexed estimation {estimation.estimation_id} for user {estimation.user_id}")


async def search_similar(user_id: int, query: str, limit: int = 5) -> list[dict]:
    collection = _collection(user_id)
    client = get_client()

    try:
        vector = await _embed(query)
        results = await client.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit,
        )
        return [r.payload for r in results]
    except Exception as e:
        logger.warning(f"Estimation search failed for user {user_id}: {e}")
        return []
