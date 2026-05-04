# -*- coding: utf-8 -*-
"""
CRUD helpers for the 'estimations' collection.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.mongodb.client import get_database
from db.mongodb.models import Estimation


async def save_estimation(
    user_id: int,
    task: str,
    total_hours: float,
    complexity: int,
    tech_stack: list[str],
    breakdown: dict,
    project_id: Optional[str] = None,
    project_name: str = "",
    reminder_at: "datetime | None" = None,
    scope: list[str] | None = None,
    estimation_mode: str = "realistic",
    task_name: str = "",
) -> Estimation:
    """
    Create a new estimation document with a generated UUID and persist it.

    :param user_id: Telegram user ID.
    :param task: Task description text.
    :param total_hours: Estimated total hours.
    :param complexity: Complexity score from 1 to 5.
    :param tech_stack: List of technologies involved.
    :param breakdown: Dict with per-phase or per-component hour breakdown.
    :param project_id: Optional project UUID this estimation belongs to.
    :param project_name: Optional human-readable project name.
    :return: Newly created and persisted Estimation instance.
    """
    estimation = Estimation(
        estimation_id=str(uuid.uuid4()),
        user_id=user_id,
        project_id=project_id,
        project_name=project_name,
        task_name=task_name,
        task=task,
        total_hours=total_hours,
        complexity=complexity,
        tech_stack=tech_stack,
        breakdown=breakdown,
        scope=scope or [],
        estimation_mode=estimation_mode,
        reminder_at=reminder_at,
    )
    await get_database()["estimations"].insert_one(estimation.model_dump())
    return estimation


async def get_estimation(estimation_id: str) -> Optional[Estimation]:
    """
    Fetch a single estimation by UUID, returning None if not found.

    :param estimation_id: Estimation UUID string.
    :return: Estimation instance or None.
    """
    doc = await get_database()["estimations"].find_one({"estimation_id": estimation_id})
    return Estimation(**doc) if doc else None


async def set_status(estimation_id: str, status: str) -> None:
    """
    Update the lifecycle status of an estimation.

    :param estimation_id: Estimation UUID string.
    :param status: New status value — one of 'in_progress', 'done', 'cancelled'.
    :return: None
    """
    await get_database()["estimations"].update_one(
        {"estimation_id": estimation_id},
        {"$set": {"status": status}},
    )


async def set_actual_hours(estimation_id: str, actual_hours: float) -> None:
    """
    Record the real hours spent so accuracy can be tracked over time.

    :param estimation_id: Estimation UUID string.
    :param actual_hours: Real hours the task took.
    :return: None
    """
    await get_database()["estimations"].update_one(
        {"estimation_id": estimation_id},
        {"$set": {"actual_hours": actual_hours}},
    )


async def get_user_estimations(user_id: int, limit: int = 20) -> list[Estimation]:
    """
    Return the most recent estimations for a user, newest first.

    :param user_id: Telegram user ID.
    :param limit: Maximum number of records to return.
    :return: List of Estimation instances sorted by created_at descending.
    """
    cursor = get_database()["estimations"].find(
        {"user_id": user_id},
        sort=[("created_at", -1)],  # newest first
        limit=limit,
    )
    return [Estimation(**doc) async for doc in cursor]


async def get_pending_reminders() -> list[Estimation]:
    """Return estimations due for a reminder.

    No actual hours recorded, reminder time has passed, and reminder not sent yet.

    :return: List of Estimation instances needing a reminder.
    """
    now = datetime.now(timezone.utc)
    cursor = get_database()["estimations"].find(
        {
            "actual_hours": None,
            "reminder_at": {"$lte": now},
            "reminder_sent_at": None,
        }
    )
    return [Estimation(**doc) async for doc in cursor]


_KEYWORD_GROUPS: dict[str, list[str]] = {
    "API / Интеграции": [
        "api",
        "webhook",
        "integration",
        "інтеграц",
        "интеграц",
        "nova poshta",
        "stripe",
        "monobank",
        "oauth",
    ],
    "Аутентификация": ["auth", "login", "аутентификац", "автентифікац", "jwt"],
    "Celery / Очереди": ["celery", "queue", "очеред", "worker"],
    "UI / Frontend": ["ui", "frontend", "верстк", "компонент", "форм", "dashboard", "кабинет", "кабінет"],
    "База данных": ["migration", "mongo", "database", "модел", "модель"],
}


def _classify_task(task: str) -> str | None:
    """
    Return the first matching keyword group name, or None if no group matches.

    :param task: Task description string.
    :return: Group name string or None.
    """
    task_lower = task.lower()
    for group, keywords in _KEYWORD_GROUPS.items():
        if any(kw in task_lower for kw in keywords):
            return group
    return None


async def get_velocity_stats(user_id: int, days: int = 30) -> dict:
    """
    Aggregate estimation accuracy stats for a user over the last N days.

    Returns a dict with keys: total, with_actual, avg_deviation, best_type,
    worst_type, top_underestimated. accuracy fields are None when no actuals exist.

    :param user_id: Telegram user ID.
    :param days: Look-back window in days.
    :return: Stats dict.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = get_database()["estimations"].find({"user_id": user_id, "created_at": {"$gte": since}})
    all_estimations = [Estimation(**doc) async for doc in cursor]

    total = len(all_estimations)
    with_actual = [e for e in all_estimations if e.actual_hours is not None and e.total_hours > 0]

    empty = {
        "total": total,
        "with_actual": 0,
        "avg_deviation": None,
        "best_type": None,
        "worst_type": None,
        "top_underestimated": [],
    }
    if not with_actual:
        return empty

    deviations = [(e.task, round((e.actual_hours - e.total_hours) / e.total_hours * 100, 1)) for e in with_actual]
    avg_dev = round(sum(d for _, d in deviations) / len(deviations), 1)

    group_devs: dict[str, list[float]] = {}
    for task, dev in deviations:
        group = _classify_task(task)
        if group:
            group_devs.setdefault(group, []).append(dev)

    group_avgs = {g: round(sum(devs) / len(devs), 1) for g, devs in group_devs.items()}
    best_type = min(group_avgs.items(), key=lambda x: abs(x[1])) if group_avgs else None
    worst_type = max(group_avgs.items(), key=lambda x: x[1]) if group_avgs else None

    sorted_under = sorted(deviations, key=lambda x: x[1], reverse=True)
    top_underestimated = [(name[:60], dev) for name, dev in sorted_under[:3] if dev > 0]

    return {
        "total": total,
        "with_actual": len(with_actual),
        "avg_deviation": avg_dev,
        "best_type": best_type,
        "worst_type": worst_type,
        "top_underestimated": top_underestimated,
    }


async def mark_reminder_sent(estimation_id: str) -> None:
    """
    Record that the reminder was sent so it is not sent again.

    :param estimation_id: Estimation UUID string.
    :return: None
    """
    now = datetime.now(timezone.utc)
    await get_database()["estimations"].update_one(
        {"estimation_id": estimation_id},
        {"$set": {"reminder_sent_at": now}},
    )
