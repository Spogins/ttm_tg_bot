# -*- coding: utf-8 -*-
"""
sprint_planner_node: stub for the sprint intent.

Full implementation is planned for a later phase.
"""
from agent.graph.state import AgentState


async def sprint_planner_node(state: AgentState) -> dict:
    """
    Return a placeholder response for the sprint planning intent.

    :param state: Current agent state with intent set to sprint.
    :return: Updated state dict with formatted_response.
    """
    return {"formatted_response": "Планировщик спринта будет доступен в следующей версии."}
