# -*- coding: utf-8 -*-
"""
project_context_node: fetch top-5 relevant project chunks from Qdrant.
"""
from loguru import logger

from agent.graph.state import AgentState
from services.indexer import search_project


async def project_context_node(state: AgentState) -> dict:
    """
    Search the Qdrant project collection for the 5 most relevant chunks.

    :param state: Current agent state.
    :return: Updated state dict with project_context list of text chunks.
    """
    project_id = state.get("project_id")
    if not project_id:  # no active project
        return {"project_context": []}

    try:
        results = await search_project(project_id, state["user_input"], limit=5)
        chunks = [r["text"] for r in results]  # extract text from search payload
    except Exception as e:
        logger.warning(f"project_context_node error for project={project_id}: {e}")
        chunks = []  # project not indexed yet

    logger.info(f"project_context_node: {len(chunks)} chunks for project={project_id}")
    return {"project_context": chunks}
