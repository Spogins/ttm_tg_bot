# -*- coding: utf-8 -*-
"""
response_formatter node: build the final Telegram-ready Markdown string from graph state.

No LLM call — pure formatting.
"""
from agent.graph.state import AgentState

_COMPLEXITY_LABEL = {1: "Trivial", 2: "Simple", 3: "Medium", 4: "Hard", 5: "Very hard"}
_CONFIDENCE_EMOJI = {"high": "🟢", "medium": "🟡", "low": "🔴"}


def _format_estimation(state: AgentState) -> str:
    """
    Build the estimation result block as Telegram Markdown.

    :param state: Current agent state with a populated estimation field.
    :return: Formatted Markdown string.
    """
    est = state.get("estimation")
    if est is None:  # estimation failed upstream
        return "❌ Не удалось сформировать оценку. Попробуйте уточнить задачу."

    subtasks_lines = "\n".join(f"  • {s['name']} — *{s['hours']}h*" for s in est["subtasks"])
    complexity_label = _COMPLEXITY_LABEL.get(est["complexity"], str(est["complexity"]))  # fallback to raw int
    confidence_emoji = _CONFIDENCE_EMOJI.get(est["confidence"], "")  # unknown confidence → no emoji

    lines = [
        "📋 *Оценка задачи*",
        "",
        "*Подзадачи:*",
        subtasks_lines,
        "",
        f"⏱ *Итого:* {est['total_hours']}h",
        f"📊 *Сложность:* {complexity_label} ({est['complexity']}/5)",
        f"🎯 *Уверенность:* {confidence_emoji} {est['confidence']}",
    ]

    risks = state.get("risks") or []
    if risks:
        risk_lines = "\n".join(f"  ⚠️ {r}" for r in risks)
        lines += ["", "*Риски:*", risk_lines]

    similar = state.get("similar_tasks") or []
    if similar:
        sim_lines = "\n".join(f"  📌 {t.get('task', '')[:60]} → {t.get('total_hours', '?')}h" for t in similar)
        lines += ["", "*Похожие задачи:*", sim_lines]

    return "\n".join(lines)


def _format_clarification(state: AgentState) -> str:
    """
    Build the clarification request block as Telegram Markdown.

    :param state: Current agent state with a populated clarification_question field.
    :return: Formatted Markdown string.
    """
    return "🤔 *Нужно уточнить задачу*\n\n" + state.get("clarification_question", "Опишите задачу подробнее.")


async def response_formatter(state: AgentState) -> dict:
    """
    Compose the final formatted_response from estimation, risks, and similar tasks.

    :param state: Current agent state.
    :return: Updated state dict with formatted_response string.
    """
    if state.get("clarification_needed"):
        text = _format_clarification(state)
    else:
        text = _format_estimation(state)

    return {"formatted_response": text}
