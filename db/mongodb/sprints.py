# -*- coding: utf-8 -*-
"""
CRUD helpers for the 'sprints' collection.
"""
import uuid
from typing import Optional

from agent.graph.state import SprintPlan
from db.mongodb.client import get_database
from db.mongodb.models import Sprint


async def save_sprint(
    user_id: int,
    project_id: Optional[str],
    project_name: str,
    hours_per_day: float,
    tasks_input: list[str],
    sprint_plan: SprintPlan,
) -> Sprint:
    """
    Persist a sprint plan document and return the saved instance.

    :param user_id: Telegram user ID.
    :param project_id: Active project UUID or None.
    :param project_name: Human-readable project name.
    :param hours_per_day: Daily capacity in hours.
    :param tasks_input: Original task strings from the user.
    :param sprint_plan: Packed sprint plan produced by sprint_planner_node.
    :return: Newly created Sprint instance.
    """
    sprint = Sprint(
        sprint_id=str(uuid.uuid4()),
        user_id=user_id,
        project_id=project_id,
        project_name=project_name,
        hours_per_day=hours_per_day,
        tasks_input=tasks_input,
        days=sprint_plan["days"],
        total_hours=sprint_plan["total_hours"],
        warnings=sprint_plan["warnings"],
    )
    await get_database()["sprints"].insert_one(sprint.model_dump())
    return sprint
