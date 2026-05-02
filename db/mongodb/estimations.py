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
    doc = await get_database()["estimations"].find_one({"estimation_id": estimation_id})
    return Estimation(**doc) if doc else None


async def set_actual_hours(estimation_id: str, actual_hours: float) -> None:
    await get_database()["estimations"].update_one(
        {"estimation_id": estimation_id},
        {"$set": {"actual_hours": actual_hours}},
    )


async def get_user_estimations(user_id: int, limit: int = 20) -> list[Estimation]:
    cursor = get_database()["estimations"].find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
        limit=limit,
    )
    return [Estimation(**doc) async for doc in cursor]
