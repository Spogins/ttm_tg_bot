# -*- coding: utf-8 -*-
"""
Index and search project structure vectors in Qdrant using Voyage AI embeddings.
"""
from typing import Literal

import voyageai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from qdrant_client.models import Distance, PointStruct

from config.settings import settings
from db.mongodb import projects as projects_db
from db.mongodb.models import ProjectTemplate
from db.qdrant.client import ensure_collection, get_client
from services.project_parser import ParsedProject

ChunkType = Literal["description", "structure", "module", "tech", "template"]

EMBEDDING_DIM = 1024  # voyage-code-3
COLLECTION_PREFIX = "project"

_voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key)
# 50-token overlap preserves context across chunk boundaries
_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


async def _embed(texts: list[str]) -> list[list[float]]:
    """
    Return embeddings for a batch of texts using the configured Voyage AI model.

    :param texts: List of text strings to embed.
    :return: List of embedding vectors, one per input text.
    """
    result = await _voyage.embed(texts, model=settings.embedding_model)
    return result.embeddings


def _build_chunks(parsed: ParsedProject, description: str = "") -> list[tuple[str, ChunkType]]:
    """
    Split a ParsedProject into (text, type) chunks: description, tech, module, and structure chunks.

    :param parsed: ParsedProject containing files, tech stack, and modules.
    :param description: Optional free-text project description provided by the user.
    :return: List of (text, chunk_type) tuples ready for embedding.
    """
    chunks: list[tuple[str, ChunkType]] = []

    # description chunk first — highest priority context for estimation
    if description:
        chunks.append((f"Project description: {description}", "description"))

    # tech chunk
    if parsed.tech_stack:
        chunks.append((f"Tech stack: {', '.join(parsed.tech_stack)}", "tech"))

    # module chunks
    for module in parsed.modules:
        module_files = [f for f in parsed.files if f.startswith(module + "/")]
        text = f"Module: {module}\nFiles:\n" + "\n".join(  # noqa: E231
            module_files[:50]
        )  # cap at 50 files to keep chunk size reasonable
        chunks.append((text, "module"))

    # structure chunks (remaining files split by RecursiveCharacterTextSplitter)
    all_files_text = "\n".join(parsed.files)
    for part in _splitter.split_text(all_files_text):
        chunks.append((part, "structure"))

    return chunks


async def index_project(project_id: str, parsed: ParsedProject, description: str = "") -> int:
    """
    Embed and upsert all project chunks into Qdrant; return the number of points stored.

    :param project_id: Project UUID used to derive the collection name.
    :param parsed: ParsedProject with the structure to index.
    :param description: Optional free-text project description to index as a dedicated chunk.
    :return: Number of vector points upserted into Qdrant.
    """
    collection = f"{COLLECTION_PREFIX}_{project_id}_docs"
    await ensure_collection(collection, vector_size=EMBEDDING_DIM, distance=Distance.COSINE)

    chunks = _build_chunks(parsed, description)
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
    response = await client.query_points(
        collection_name=collection,
        query=vectors[0],
        limit=limit,
    )
    return [{"text": r.payload["text"], "type": r.payload["type"], "score": r.score} for r in response.points]


async def index_template(project_id: str, template: ProjectTemplate) -> None:
    """
    Embed a completed-estimation template and upsert it into the project's Qdrant collection.

    Templates are stored with ``type="template"`` so ``search_project`` returns them alongside
    structure chunks; callers can recognise them by checking ``result["type"] == "template"``.

    The text indexed encodes all fields useful as few-shot context for the LLM: task description,
    planned/actual hours, deviation, and scope.

    :param project_id: Project UUID used to derive the collection name.
    :param template: Fully-constructed ProjectTemplate instance.
    :return: None
    """
    collection = f"{COLLECTION_PREFIX}_{project_id}_docs"
    await ensure_collection(collection, vector_size=EMBEDDING_DIM, distance=Distance.COSINE)

    sign = "+" if template.deviation_pct >= 0 else ""
    scope_str = ", ".join(template.scope) if template.scope else "—"
    text = (
        f"Template: {template.name}\n"
        f"Task: {template.task}\n"
        f"Planned: {template.total_hours}h | Actual: {template.actual_hours}h | "
        f"Deviation: {sign}{template.deviation_pct:.0f}%\n"  # noqa: E231
        f"Scope: {scope_str}"
    )

    vectors = await _embed([text])

    # UUID-derived point ID: top 63 bits of the template UUID, stable across process restarts.
    # hash() is PYTHONHASHSEED-dependent and would produce different IDs after restart,
    # causing duplicate Qdrant points that are never cleaned up.
    import uuid as _uuid

    point_id = _uuid.UUID(template.template_id).int >> 65
    point = PointStruct(
        id=point_id,
        vector=vectors[0],
        payload={
            "text": text,
            "type": "template",
            "template_id": template.template_id,
            "deviation_pct": template.deviation_pct,
            "total_hours": template.total_hours,
            "actual_hours": template.actual_hours,
        },
    )

    client = get_client()
    await client.upsert(collection_name=collection, points=[point])
    logger.info(f"Indexed template {template.template_id} for project {project_id}")


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
