# -*- coding: utf-8 -*-
"""
Index and search per-user estimation vectors in Qdrant using Voyage AI embeddings.
"""
import voyageai
from loguru import logger
from qdrant_client.models import Distance, PointStruct

from config.settings import settings
from db.mongodb.models import Estimation
from db.qdrant.client import ensure_collection, get_client

EMBEDDING_DIM = 1024  # voyage-code-3
COLLECTION_PREFIX = "estimations"

_voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)


def _collection(user_id: int) -> str:
    """
    Return the Qdrant collection name for a user's estimations.

    :param user_id: Telegram user ID.
    :return: Collection name string.
    """
    return f"{COLLECTION_PREFIX}_{user_id}"


async def _embed(text: str) -> list[float]:
    """
    Return a single embedding vector for the given text.

    :param text: Text string to embed.
    :return: Embedding vector as a list of floats.
    """
    result = await _voyage.embed([text], model=settings.embedding_model)  # API expects a list
    return result.embeddings[0]  # single text → first element


def _estimation_text(estimation: Estimation) -> str:
    """
    Serialize an estimation to a plain-text string suitable for embedding.

    :param estimation: Estimation model instance.
    :return: Multi-line text representation of the estimation.
    """
    return (
        f"Task: {estimation.task}\n"
        f"Tech: {', '.join(estimation.tech_stack)}\n"
        f"Project: {estimation.project_name}\n"
        f"Hours: {estimation.total_hours}, Complexity: {estimation.complexity}"
    )


def _point_id_from_estimation_id(estimation_id: str) -> int:
    """
    Derive a stable int64 Qdrant point ID from an estimation UUID string.

    :param estimation_id: Estimation UUID string.
    :return: Non-negative int64 point ID.
    """
    return abs(hash(estimation_id)) % (2**63)


async def index_estimation(estimation: Estimation) -> None:
    """
    Embed and upsert one estimation into the user's Qdrant collection.

    :param estimation: Estimation model instance to index.
    :return: None
    """
    collection = _collection(estimation.user_id)
    await ensure_collection(collection, vector_size=EMBEDDING_DIM, distance=Distance.COSINE)

    text = _estimation_text(estimation)
    vector = await _embed(text)

    point = PointStruct(
        id=_point_id_from_estimation_id(estimation.estimation_id),
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
    """
    Find past estimations semantically similar to the query; returns empty list on error.

    :param user_id: Telegram user ID whose collection to search.
    :param query: Natural-language search query.
    :param limit: Maximum number of results to return.
    :return: List of estimation payload dicts, or empty list if the collection is missing.
    """
    collection = _collection(user_id)
    client = get_client()

    try:
        vector = await _embed(query)
        results = await client.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit,
        )
        return [r.payload for r in results]  # strip Qdrant wrapper
    except Exception as e:
        logger.warning(f"Estimation search failed for user {user_id}: {e}")
        return []  # collection absent for new users


async def update_actual_hours(estimation_id: str, user_id: int, actual_hours: float) -> None:
    """
    Update the actual_hours field in the Qdrant payload for an existing estimation point.

    :param estimation_id: Estimation UUID string.
    :param user_id: Telegram user ID whose collection to update.
    :param actual_hours: Real hours the task took.
    :return: None
    """
    collection = _collection(user_id)
    point_id = _point_id_from_estimation_id(estimation_id)
    client = get_client()
    await client.set_payload(
        collection_name=collection,
        payload={"actual_hours": actual_hours},
        points=[point_id],
    )
    logger.info(f"Updated actual_hours={actual_hours} for estimation {estimation_id}")
