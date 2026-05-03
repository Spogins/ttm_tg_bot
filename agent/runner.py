# -*- coding: utf-8 -*-
"""
Graph runner: loads conversation history, invokes the agent graph, and persists the result.
"""
from loguru import logger

from agent.graph.graph import graph
from agent.graph.state import AgentState
from db.mongodb import history as history_db
from db.mongodb import users as users_db

# returned on unrecoverable graph errors so the caller always gets a string
_ERROR_RESPONSE = "Произошла ошибка при обработке запроса. Попробуйте ещё раз."


async def run_agent(
    user_id: int,
    user_input: str,
    project_id: str | None = None,
    scope: list[str] | None = None,
) -> dict:
    """
    Run the full estimation pipeline and return the complete final state.

    Loads conversation history from MongoDB, invokes the compiled LangGraph,
    then persists both the user message and the agent reply.

    :param user_id: Telegram user ID.
    :param user_input: Raw text from the user (already transcribed if voice).
    :param project_id: Active project UUID, or None if no project is selected.
    :param scope: Optional list of scope labels (e.g. ["backend", "qa"]).
    :return: Final AgentState dict; on error contains only 'formatted_response'.
    """
    conversation_history = await history_db.get_history(user_id)

    initial_state: AgentState = {
        "user_id": user_id,
        "project_id": project_id,
        "user_input": user_input,
        "intent": "unknown",  # set by intent_classifier
        "project_context": [],
        "similar_tasks": [],
        "clarification_needed": False,
        "clarification_question": "",
        "estimation": None,
        "risks": [],
        "formatted_response": "",
        "tokens_used": 0,
        "conversation_history": conversation_history,
        "sprint_hours_per_day": None,
        "sprint_tasks": None,
        "sprint_plan": None,
        "scope": scope or [],
    }

    try:
        result: dict = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"run_agent error for user={user_id}: {e}")
        return {"formatted_response": _ERROR_RESPONSE}

    response = result.get("formatted_response", "")

    # persist both sides so the next call has full context
    await history_db.append_messages(
        user_id,
        [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response},
        ],
    )

    logger.info(f"run_agent: user={user_id} intent={result.get('intent')} " f"tokens={result.get('tokens_used', 0)}")
    return result


async def run_agent_for_message(user_id: int, user_input: str) -> str:
    """
    Resolve the active project and return only the formatted response text.

    :param user_id: Telegram user ID.
    :param user_input: Raw text from the user.
    :return: Formatted response string ready to send to Telegram.
    """
    user = await users_db.get_user(user_id)
    project_id = user.active_project_id if user else None
    result = await run_agent(user_id, user_input, project_id=project_id)
    return result.get("formatted_response", _ERROR_RESPONSE)


async def run_sprint_agent(
    user_id: int,
    project_id: str | None,
    hours_per_day: float,
    tasks: list[str],
) -> dict:
    """
    Build a sprint-specific AgentState and run the graph to produce a sprint plan.

    Does NOT persist conversation history — sprint planning is a one-shot operation.

    :param user_id: Telegram user ID.
    :param project_id: Active project UUID, or None.
    :param hours_per_day: Daily capacity provided by the user.
    :param tasks: List of task description strings (1–10 items).
    :return: Final AgentState dict; on error contains only 'formatted_response'.
    """
    initial_state: AgentState = {
        "user_id": user_id,
        "project_id": project_id,
        "user_input": "",
        "intent": "unknown",
        "project_context": [],
        "similar_tasks": [],
        "clarification_needed": False,
        "clarification_question": "",
        "estimation": None,
        "risks": [],
        "formatted_response": "",
        "tokens_used": 0,
        "conversation_history": [],
        "sprint_hours_per_day": hours_per_day,
        "sprint_tasks": tasks,
        "sprint_plan": None,
        "scope": [],
    }

    try:
        result: dict = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"run_sprint_agent error for user={user_id}: {e}")
        return {"formatted_response": _ERROR_RESPONSE}

    logger.info(f"run_sprint_agent: user={user_id} tasks={len(tasks)} " f"tokens={result.get('tokens_used', 0)}")
    return result
