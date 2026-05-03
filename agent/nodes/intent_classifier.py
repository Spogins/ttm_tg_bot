# -*- coding: utf-8 -*-
"""
intent_classifier node: route user input to the correct sub-graph branch.

Uses Claude Haiku to keep token cost low.
"""
from loguru import logger

from agent.graph.state import AgentState, Intent
from agent.llm import HAIKU_MODEL, get_client
from db.mongodb import users as users_db

_SYSTEM = (
    "You are an intent classifier for a software task estimation bot. "
    "Classify the user message into exactly one of these intents:\n"
    "  estimate       — user wants to estimate a development task\n"
    "  project_add    — user wants to add or upload a project\n"
    "  project_switch — user wants to switch the active project\n"
    "  sprint         — user asks about sprint planning\n"
    "  history        — user wants to see past estimations\n"
    "  unknown        — anything else\n\n"
    "Reply with the single intent word only, no punctuation."
)

_VALID: set[Intent] = {"estimate", "project_add", "project_switch", "sprint", "history", "unknown"}


async def intent_classifier(state: AgentState) -> dict:
    """
    Classify user_input intent with Haiku; falls back to 'unknown' on error.

    Includes the last 2 conversation history messages so that clarification
    answers are correctly classified as 'estimate' rather than 'unknown'.

    :param state: Current agent state.
    :return: Updated state dict with intent and tokens_used.
    """
    client = get_client()
    try:
        # prepend last 2 history turns so the classifier sees clarification context
        messages = [{"role": m["role"], "content": m["content"]} for m in state.get("conversation_history", [])[-2:]]
        messages.append({"role": "user", "content": state["user_input"]})

        response = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=10,
            system=_SYSTEM,
            messages=messages,
        )
        raw: str = response.content[0].text.strip().lower()
        intent: Intent = (
            raw if raw in _VALID else "unknown"
        )  # guard against hallucinated values  # type: ignore[assignment]
        tokens = response.usage.input_tokens + response.usage.output_tokens
    except Exception as e:
        logger.error(f"intent_classifier error: {e}")
        intent = "unknown"  # safe fallback on API error
        tokens = 0

    await users_db.increment_tokens(state["user_id"], tokens)  # persist regardless of outcome
    logger.info(f"user={state['user_id']} intent={intent} tokens={tokens}")
    return {"intent": intent, "tokens_used": tokens}
