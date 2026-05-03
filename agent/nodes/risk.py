# -*- coding: utf-8 -*-
"""
risk_node: identify up to 3 development risks for the estimated task using Haiku.
"""
from loguru import logger

from agent.graph.state import AgentState
from agent.llm import HAIKU_MODEL, get_client
from db.mongodb import users as users_db

_SYSTEM = (
    "You are a tech lead doing a quick risk assessment. "
    "Given the task description, list up to 3 development risks. "
    "Each risk must be one short phrase (max 10 words). "
    "Output one risk per line, no numbering, no intro. "
    "Use the same language as the user's message."
)


async def risk_node(state: AgentState) -> dict:
    """
    Call Haiku to identify up to 3 risks; returns an empty list on failure.

    :param state: Current agent state.
    :return: Updated state dict with risks list and tokens_used.
    """
    client = get_client()
    tokens = 0
    risks: list[str] = []

    try:
        response = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=150,
            system=_SYSTEM,
            messages=[{"role": "user", "content": state["user_input"]}],
        )
        tokens = response.usage.input_tokens + response.usage.output_tokens
        raw = response.content[0].text.strip()
        risks = [line.strip() for line in raw.splitlines() if line.strip()][:3]  # cap at 3
    except Exception as e:
        logger.error(f"risk_node error: {e}")  # risks stay empty, non-blocking

    await users_db.increment_tokens(state["user_id"], tokens)  # persist token spend
    logger.info(f"risk_node: {len(risks)} risks for user={state['user_id']}, tokens={tokens}")
    return {"risks": risks, "tokens_used": tokens}
