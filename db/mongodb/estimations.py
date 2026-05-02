"""
CRUD helpers for the 'estimations' collection.
"""
import uuid
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
        task=task,
        total_hours=total_hours,
        complexity=complexity,
        tech_stack=tech_stack,
        breakdown=breakdown,
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
