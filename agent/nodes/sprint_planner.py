# -*- coding: utf-8 -*-
"""
sprint_planner_node: estimates a list of tasks and packs them into days.
"""
import re

from loguru import logger

from agent.graph.state import AgentState, SprintDay, SprintPlan, SprintTaskResult
from agent.nodes.estimation import estimation_node
from db.mongodb import projects as projects_db
from db.mongodb import sprints as sprints_db

_API_KEYWORDS = frozenset(
    {
        "api",
        "webhook",
        "integration",
        "nova poshta",
        "stripe",
        "oauth",
        "telegram",
        "monobank",
    }
)
_API_BUFFER = 1.20


def _has_api_keywords(task_name: str, subtask_names: list[str]) -> bool:
    """Return True if the task or any subtask mentions external API keywords."""
    combined = " ".join([task_name] + subtask_names).lower()
    return any(re.search(r"\b" + re.escape(kw) + r"\b", combined) for kw in _API_KEYWORDS)


def _pack_into_days(
    tasks: list[SprintTaskResult],
    hours_per_day: float,
) -> list[SprintDay]:
    """Pack tasks into days using First-Fit Decreasing bin packing.

    Sort tasks largest-first, place each in the first day with sufficient
    remaining capacity. Oversized tasks always get their own day.
    """
    sorted_tasks = sorted(tasks, key=lambda t: t["hours"], reverse=True)
    days: list[dict] = []

    for task in sorted_tasks:
        if task["hours"] > hours_per_day:
            days.append({"day": len(days) + 1, "tasks": [task], "total_hours": round(task["hours"], 1)})
            continue
        placed = False
        for day in days:
            remaining = round(hours_per_day - day["total_hours"], 10)
            if remaining >= task["hours"]:
                day["tasks"].append(task)
                day["total_hours"] = round(day["total_hours"] + task["hours"], 1)
                placed = True
                break
        if not placed:
            days.append({"day": len(days) + 1, "tasks": [task], "total_hours": round(task["hours"], 1)})

    return days


def _build_warnings(tasks: list[SprintTaskResult], hours_per_day: float) -> list[str]:
    """Collect human-readable warnings for risky tasks."""
    warnings = []
    for task in tasks:
        if task["hours"] > hours_per_day:
            warnings.append(f"⚠️ «{task['name']}» занимает {task['hours']} ч — больше одного дня")
        if task["confidence"] == "low":
            warnings.append(f"⚠️ «{task['name']}»: низкая уверенность в оценке")
        if task["complexity"] == 5:
            warnings.append(f"⚠️ «{task['name']}»: очень высокая сложность, рассмотрите декомпозицию")
    return warnings


async def sprint_planner_node(state: AgentState) -> dict:
    """
    Evaluate each sprint task, apply API buffer, pack into days, persist.

    Reads sprint_tasks and sprint_hours_per_day from state.
    Writes sprint_plan and tokens_used back to state.
    """
    tasks_input: list[str] = state.get("sprint_tasks") or []
    hours_per_day: float = state.get("sprint_hours_per_day") or 8.0
    total_tokens = 0
    evaluated: list[SprintTaskResult] = []

    for task_text in tasks_input:
        minimal_state: AgentState = {
            **state,
            "user_input": task_text,
            "intent": "estimate",
            "project_context": [],
            "similar_tasks": [],
            "clarification_needed": False,
            "clarification_question": "",
            "estimation": None,
            "risks": [],
            "formatted_response": "",
            "tokens_used": 0,
            "conversation_history": [],
        }
        result = await estimation_node(minimal_state)
        total_tokens += result.get("tokens_used", 0)
        estimation = result.get("estimation")

        if estimation is None:
            logger.warning(f"sprint_planner_node: estimation failed for task '{task_text}'")
            evaluated.append(
                SprintTaskResult(
                    name=task_text,
                    hours=0.0,
                    has_api_buffer=False,
                    complexity=1,
                    confidence="low",
                )
            )
            continue

        subtask_names = [s["name"] for s in estimation["subtasks"]]
        has_api = _has_api_keywords(task_text, subtask_names)
        hours = round(estimation["total_hours"] * _API_BUFFER, 1) if has_api else round(estimation["total_hours"], 1)

        evaluated.append(
            SprintTaskResult(
                name=task_text,
                hours=hours,
                has_api_buffer=has_api,
                complexity=estimation["complexity"],
                confidence=estimation["confidence"],
            )
        )

    days = _pack_into_days(evaluated, hours_per_day)
    warnings = _build_warnings(evaluated, hours_per_day)
    total_hours = round(sum(t["hours"] for t in evaluated), 1)

    project = await projects_db.get_project(state.get("project_id")) if state.get("project_id") else None
    project_name = project.name if project else ""

    sprint_plan: SprintPlan = {
        "project_name": project_name,
        "days": days,
        "total_hours": total_hours,
        "warnings": warnings,
    }

    try:
        await sprints_db.save_sprint(
            user_id=state["user_id"],
            project_id=state.get("project_id"),
            project_name=project_name,
            hours_per_day=hours_per_day,
            tasks_input=tasks_input,
            sprint_plan=sprint_plan,
        )
    except Exception as e:
        logger.warning(f"sprint_planner_node: failed to save sprint: {e}")

    logger.info(
        f"sprint_planner_node: user={state['user_id']} tasks={len(tasks_input)} "
        f"days={len(days)} total={total_hours}h tokens={total_tokens}"
    )
    return {"sprint_plan": sprint_plan, "tokens_used": total_tokens}
