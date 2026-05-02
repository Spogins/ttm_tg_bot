"""
Index and search project structure vectors in Qdrant using OpenAI embeddings.
"""
import asyncio
from typing import Literal

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from qdrant_client.models import PointStruct, Distance
from loguru import logger

from config.settings import settings
from db.mongodb import projects as projects_db
from db.qdrant.client import ensure_collection, get_client
from services.project_parser import ParsedProject

ChunkType = Literal["structure", "module", "tech"]

EMBEDDING_DIM = 1536  # text-embedding-3-small
COLLECTION_PREFIX = "project"

_openai = AsyncOpenAI(api_key=settings.openai_api_key)
# 50-token overlap preserves context across chunk boundaries
_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


async def _embed(texts: list[str]) -> list[list[float]]:
    """
    Return embeddings for a batch of texts using the configured OpenAI model.

    :param texts: List of text strings to embed.
    :return: List of embedding vectors, one per input text.
    """
    response = await _openai.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def _build_chunks(parsed: ParsedProject) -> list[tuple[str, ChunkType]]:
    """
    Split a ParsedProject into (text, type) chunks: one tech chunk, per-module chunks, and structure chunks.

    :param parsed: ParsedProject containing files, tech stack, and modules.
    :return: List of (text, chunk_type) tuples ready for embedding.
    """
    chunks: list[tuple[str, ChunkType]] = []

    # tech chunk
    if parsed.tech_stack:
        chunks.append((f"Tech stack: {', '.join(parsed.tech_stack)}", "tech"))

    # module chunks
    for module in parsed.modules:
        module_files = [f for f in parsed.files if f.startswith(module + "/")]
        text = f"Module: {module}\nFiles:\n" + "\n".join(module_files[:50])  # cap at 50 files to keep chunk size reasonable
        chunks.append((text, "module"))

    # structure chunks (remaining files split by RecursiveCharacterTextSplitter)
    all_files_text = "\n".join(parsed.files)
    for part in _splitter.split_text(all_files_text):
        chunks.append((part, "structure"))

    return chunks


async def index_project(project_id: str, parsed: ParsedProject) -> int:
    """
    Embed and upsert all project chunks into Qdrant; return the number of points stored.

    :param project_id: Project UUID used to derive the collection name.
    :param parsed: ParsedProject with the structure to index.
    :return: Number of vector points upserted into Qdrant.
    """
    collection = f"{COLLECTION_PREFIX}_{project_id}_docs"
    await ensure_collection(collection, vector_size=EMBEDDING_DIM, distance=Distance.COSINE)

    chunks = _build_chunks(parsed)
    if not chunks:
        logger.warning(f"No chunks for project {project_id}")
        return 0

    texts = [c[0] for c in chunks]
    types = [c[1] for c in chunks]

    logger.info(f"Embedding {len(texts)} chunks for project {project_id}")
    vectors = await _embed(texts)

    # use sequential integer IDs; Qdrant requires integer point IDs (not UUIDs)
    points = [
        PointStruct(
            id=i,
            vector=vector,
            payload={"text": text, "type": chunk_type},
        )
        for i, (vector, text, chunk_type) in enumerate(zip(vectors, texts, types))
    ]

    client = get_client()
    await client.upsert(collection_name=collection, points=points)
    await projects_db.update_project(project_id, files_indexed=len(points), qdrant_collection=collection)

    logger.info(f"Indexed {len(points)} chunks for project {project_id}")
    return len(points)


async def search_project(project_id: str, query: str, limit: int = 5) -> list[dict]:
    """
    Return the top-k most relevant chunks for a natural-language query.

    :param project_id: Project UUID used to derive the collection name.
    :param query: Natural-language search query.
    :param limit: Maximum number of results to return.
    :return: List of dicts with 'text', 'type', and 'score' keys.
    """
    collection = f"{COLLECTION_PREFIX}_{project_id}_docs"
    vectors = await _embed([query])

    client = get_client()
    results = await client.search(
        collection_name=collection,
        query_vector=vectors[0],
        limit=limit,
    )
    return [{"text": r.payload["text"], "type": r.payload["type"], "score": r.score} for r in results]


async def delete_project_index(project_id: str) -> None:
    """
    Drop the Qdrant collection for the given project, ignoring errors if it does not exist.

    :param project_id: Project UUID used to derive the collection name.
    :return: None
    """
    collection = f"{COLLECTION_PREFIX}_{project_id}_docs"
    client = get_client()
    try:
        await client.delete_collection(collection)
        logger.info(f"Deleted Qdrant collection {collection}")
    except Exception as e:
        logger.warning(f"Could not delete collection {collection}: {e}")
