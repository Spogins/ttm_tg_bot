# -*- coding: utf-8 -*-
"""
input_processor node: normalise user input before it enters the graph.
"""
from agent.graph.state import AgentState


async def input_processor(state: AgentState) -> dict:
    """
    Trim and collapse whitespace in user_input.

    :param state: Current agent state.
    :return: Updated state dict with normalised user_input.
    """
    text = " ".join(state["user_input"].split())  # handles tabs and newlines too
    return {"user_input": text}
