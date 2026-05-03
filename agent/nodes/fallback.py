# -*- coding: utf-8 -*-
"""
fallback_node: handles history and unknown intents with a short informational reply.
"""
from agent.graph.state import AgentState


async def fallback_node(state: AgentState) -> dict:
    """
    Return a helpful hint when the intent is history or unrecognised.

    :param state: Current agent state with intent set to history or unknown.
    :return: Updated state dict with formatted_response.
    """
    intent = state.get("intent", "unknown")
    if intent == "history":
        text = "История оценок будет доступна в следующей версии."
    else:
        text = "Я не понял запрос. Опишите задачу для оценки или используйте /help."
    return {"formatted_response": text}
