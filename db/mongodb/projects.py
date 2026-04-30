import uuid
from datetime import datetime, timezone
from typing import Optional

from db.mongodb.client import get_database
from db.mongodb.models import Project


async def get_project(project_id: str) -> Optional[Project]:
    doc = await get_database()["projects"].find_one({"project_id": project_id})
    return Project(**doc) if doc else None


async def get_user_projects(user_id: int) -> list[Project]:
    cursor = get_database()["projects"].find({"user_id": user_id})
    return [Project(**doc) async for doc in cursor]


async def create_project(user_id: int, name: str, **kwargs) -> Project:
    project = Project(
        project_id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        **kwargs,
    )
    await get_database()["projects"].insert_one(project.model_dump())
    return project


async def update_project(project_id: str, **fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc)
    await get_database()["projects"].update_one(
        {"project_id": project_id},
        {"$set": fields},
    )


async def delete_project(project_id: str) -> None:
    await get_database()["projects"].delete_one({"project_id": project_id})
