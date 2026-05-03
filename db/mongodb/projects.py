# -*- coding: utf-8 -*-
"""
CRUD helpers for the 'projects' collection.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from db.mongodb.client import get_database
from db.mongodb.models import Project, ProjectTemplate


async def get_project(project_id: str) -> Optional[Project]:
    """
    Fetch a project by its UUID, returning None if not found.

    :param project_id: Project UUID string.
    :return: Project instance or None.
    """
    doc = await get_database()["projects"].find_one({"project_id": project_id})
    return Project(**doc) if doc else None


async def get_user_projects(user_id: int) -> list[Project]:
    """
    Return all projects belonging to the given user.

    :param user_id: Telegram user ID.
    :return: List of Project instances (may be empty).
    """
    cursor = get_database()["projects"].find({"user_id": user_id})
    return [Project(**doc) async for doc in cursor]


async def create_project(user_id: int, name: str, **kwargs) -> Project:
    """
    Insert a new project with a generated UUID and return the created document.

    :param user_id: Telegram user ID of the project owner.
    :param name: Human-readable project name.
    :param kwargs: Additional fields passed directly to the Project model.
    :return: Newly created Project instance.
    """
    project = Project(
        project_id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        **kwargs,
    )
    await get_database()["projects"].insert_one(project.model_dump())
    return project


async def update_project(project_id: str, **fields) -> None:
    """
    Patch arbitrary fields on the project and refresh updated_at.

    :param project_id: Project UUID string.
    :param fields: Field names and new values to set.
    :return: None
    """
    fields["updated_at"] = datetime.now(timezone.utc)  # always stamp the modification time
    await get_database()["projects"].update_one(
        {"project_id": project_id},
        {"$set": fields},
    )


async def delete_project(project_id: str) -> None:
    """
    Permanently remove the project document from MongoDB.

    :param project_id: Project UUID string.
    :return: None
    """
    await get_database()["projects"].delete_one({"project_id": project_id})


async def add_template(project_id: str, template: ProjectTemplate) -> None:
    """
    Append a template to the project's templates list.

    Uses $push so concurrent saves don't race. Templates are capped at 50 per project
    to prevent unbounded growth; oldest entries are dropped if the limit is exceeded.

    :param project_id: Project UUID string.
    :param template: Fully-constructed ProjectTemplate instance.
    :return: None
    """
    await get_database()["projects"].update_one(
        {"project_id": project_id},
        {
            "$push": {
                "templates": {
                    "$each": [template.model_dump()],
                    "$slice": -50,  # keep the most recent 50
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
