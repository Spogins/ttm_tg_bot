# -*- coding: utf-8 -*-
"""
project_manager_node: stub for project_add and project_switch intents.

Full implementation is planned for a later phase.
"""
from agent.graph.state import AgentState


async def project_manager_node(state: AgentState) -> dict:
    """
    Return a placeholder response for project management intents.

    :param state: Current agent state with intent set to project_add or project_switch.
    :return: Updated state dict with formatted_response.
    """
    intent = state.get("intent", "")
    if intent == "project_add":
        text = "Используйте /projects → ➕ Добавить проект для загрузки структуры проекта."
    else:  # project_switch
        text = "Используйте /projects для переключения активного проекта."
    return {"formatted_response": text}
