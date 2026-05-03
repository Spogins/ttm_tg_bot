# -*- coding: utf-8 -*-
"""
clarification_node: decide if the task description is too vague.

If vague, generate 2-3 clarifying questions with Haiku.
"""
from loguru import logger

from agent.graph.state import AgentState
from agent.llm import HAIKU_MODEL, get_client
from db.mongodb import users as users_db

_SYSTEM = (
    "You are a senior software engineer helping to clarify a vague task description. "
    "If project context is provided, use it: reference specific modules, files, or technologies "
    "that actually exist in the project instead of asking generic questions. "
    "If similar past tasks are provided, reference them to clarify scope. "
    "Generate 2-3 short, specific clarifying questions in the same language as the user's message. "
    "Format: one question per line, no numbering, no intro text."
)

# tasks shorter than this word count are always sent to clarification regardless of content
_MIN_WORDS = 20


def _needs_clarification(text: str) -> bool:
    """
    Return True if the task is too short or lacks any recognisable technical detail.

    :param text: Normalised user input.
    :return: True when clarification is required.
    """
    words = text.split()
    if len(words) < _MIN_WORDS:
        return True
    tech_hints = {
        "api",
        "endpoint",
        "database",
        "db",
        "model",
        "service",
        "auth",
        "integration",
        "backend",
        "frontend",
        "ui",
        "test",
        "deploy",
        "hook",
        "event",
        "queue",
        "cache",
        "баз",
        "сервис",
        "апи",
        "модел",
        "тест",
        "деплой",
        "интеграц",
    }
    lower = text.lower()
    return not any(hint in lower for hint in tech_hints)  # no tech keyword found


def _build_prompt(state: AgentState) -> str:
    """
    Compose the clarification prompt from project context, similar tasks, and user input.

    :param state: Current agent state.
    :return: Assembled prompt string for the Haiku call.
    """
    parts: list[str] = []

    if state.get("project_context"):
        # top 3 chunks are the most relevant to the query
        ctx = "\n".join(state["project_context"][:3])
        parts.append(f"## Project context\n{ctx}")

    if state.get("similar_tasks"):
        lines = [f"- {t.get('task', '')[:80]} → {t.get('total_hours', '?')}h" for t in state["similar_tasks"][:2]]
        parts.append("## Similar past tasks\n" + "\n".join(lines))

    parts.append(f"## Task to clarify\n{state['user_input']}")
    return "\n\n".join(parts)


async def clarification_node(state: AgentState) -> dict:
    """
    Set clarification_needed=True and generate questions if the task is vague.

    :param state: Current agent state.
    :return: Updated state dict with clarification_needed, clarification_question, and tokens_used.
    """
    if not _needs_clarification(state["user_input"]):  # task is specific enough
        return {"clarification_needed": False, "clarification_question": ""}

    client = get_client()
    tokens = 0
    question = ""
    try:
        response = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=200,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(state)}],
        )
        question = response.content[0].text.strip()
        tokens = response.usage.input_tokens + response.usage.output_tokens
    except Exception as e:
        logger.error(f"clarification_node error: {e}")
        question = "Можете описать задачу подробнее?"  # static fallback

    await users_db.increment_tokens(state["user_id"], tokens)
    logger.info(f"clarification needed for user={state['user_id']}, tokens={tokens}")
    return {
        "clarification_needed": True,
        "clarification_question": question,
        "tokens_used": tokens,
    }
