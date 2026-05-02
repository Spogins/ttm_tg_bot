# -*- coding: utf-8 -*-
"""
estimation_node: main Claude call that produces a structured EstimationResult.
"""
import json
import re

from loguru import logger

from agent.graph.state import AgentState, EstimationResult
from agent.llm import get_client
from config.settings import settings
from db.mongodb import users as users_db

_SYSTEM = """\
You are an experienced Python backend tech lead.
Estimate the development task in detail, then return a JSON object and nothing else.

Required JSON schema:
{
  "subtasks": [{"name": "<string>", "hours": <float>}],
  "total_hours": <float>,
  "complexity": <integer 1-5>,
  "confidence": "high" | "medium" | "low"
}

Rules:
- subtasks must be exhaustive and cover the full scope
- total_hours must equal the sum of subtask hours
- complexity 1=trivial, 5=very hard
- confidence reflects how clear the requirements are\
"""


def _build_user_prompt(state: AgentState, experience_level: str) -> str:
    """
    Compose the full user-side prompt from project context, history, and task text.

    :param state: Current agent state.
    :param experience_level: Developer experience level from user settings (junior/mid/senior).
    :return: Assembled prompt string.
    """
    lines: list[str] = []

    if state.get("project_context"):
        ctx = "\n".join(state["project_context"])
        lines.append(f"## Project context\n{ctx}")

    if state.get("similar_tasks"):
        parts = []
        for t in state["similar_tasks"]:
            parts.append(
                f"- {t.get('task', '')} → {t.get('total_hours', '?')}h " f"(complexity {t.get('complexity', '?')})"
            )
        lines.append("## Similar past tasks\n" + "\n".join(parts))

    if state.get("conversation_history"):
        history_lines = []
        for msg in state["conversation_history"][-5:]:  # last 5 messages only
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_lines.append(f"{role}: {content}")
        lines.append("## Conversation history\n" + "\n".join(history_lines))

    lines.append(f"## Developer experience level\n{experience_level}")
    lines.append(f"## Task to estimate\n{state['user_input']}")
    return "\n\n".join(lines)


def _parse_result(text: str) -> EstimationResult | None:
    """
    Extract and parse the JSON block from the model response.

    :param text: Raw model output that may include markdown fences.
    :return: Parsed EstimationResult, or None if parsing fails.
    """
    # model sometimes wraps the JSON in ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text.strip()
    try:
        data = json.loads(raw)
        return EstimationResult(
            subtasks=data["subtasks"],
            total_hours=float(data["total_hours"]),
            complexity=int(data["complexity"]),
            confidence=data["confidence"],
        )
    except Exception as e:
        logger.error(f"estimation_node parse error: {e}\nraw={raw[:300]}")
        return None  # caller retries on None


async def estimation_node(state: AgentState) -> dict:
    """
    Call Claude Sonnet to estimate the task; retries once on parse failure.

    :param state: Current agent state.
    :return: Updated state dict with estimation and tokens_used.
    """
    user = await users_db.get_user(state["user_id"])
    experience_level = user.settings.experience_level if user else "mid"  # default if user missing

    client = get_client()
    prompt = _build_user_prompt(state, experience_level)
    total_tokens = 0
    estimation: EstimationResult | None = None

    for attempt in range(2):  # retry once on parse failure
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            tokens = response.usage.input_tokens + response.usage.output_tokens
            total_tokens += tokens
            estimation = _parse_result(response.content[0].text)
            if estimation is not None:  # stop on first valid parse
                break
            logger.warning(f"estimation_node: parse failed on attempt {attempt + 1}, retrying")
        except Exception as e:
            logger.error(f"estimation_node error (attempt {attempt + 1}): {e}")
            break  # don't retry on API error

    await users_db.increment_tokens(state["user_id"], total_tokens)  # persist token spend
    logger.info(
        f"estimation_node: user={state['user_id']} "
        f"hours={estimation['total_hours'] if estimation else 'N/A'} "
        f"tokens={total_tokens}"
    )
    return {"estimation": estimation, "tokens_used": total_tokens}
