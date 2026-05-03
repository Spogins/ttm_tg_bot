# -*- coding: utf-8 -*-
"""
similar_tasks_node: fetch top-3 past estimations similar to the current task.
"""
from loguru import logger

from agent.graph.state import AgentState
from services.estimation_indexer import search_similar


async def similar_tasks_node(state: AgentState) -> dict:
    """
    Search the user's estimation history in Qdrant for 3 similar tasks.

    :param state: Current agent state.
    :return: Updated state dict with similar_tasks list of payload dicts.
    """
    try:
        results = await search_similar(state["user_id"], state["user_input"], limit=3)
    except Exception as e:
        logger.warning(f"similar_tasks_node error for user={state['user_id']}: {e}")
        results = []  # no history yet for new users

    logger.info(f"similar_tasks_node: {len(results)} similar tasks for user={state['user_id']}")
    return {"similar_tasks": results}
