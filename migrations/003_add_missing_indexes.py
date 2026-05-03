# -*- coding: utf-8 -*-
description = "add_missing_indexes"

import pymongo


async def up(db):
    """
    Add compound and single-field indexes to estimations, projects, sprints, and history.

    :param db: AsyncIOMotorDatabase instance.
    :return: None
    """
    # estimations: fast lookup by id, user queries sorted by date, reminder scan
    await db["estimations"].create_index("estimation_id", unique=True)
    await db["estimations"].create_index([("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
    await db["estimations"].create_index(
        [
            ("actual_hours", pymongo.ASCENDING),
            ("reminder_at", pymongo.ASCENDING),
            ("reminder_sent_at", pymongo.ASCENDING),
        ],
        sparse=True,
    )

    # projects: list all projects for a user
    await db["projects"].create_index("user_id")

    # sprints: lookup by id and list by user
    await db["sprints"].create_index("sprint_id", unique=True)
    await db["sprints"].create_index("user_id")

    # conversation history: one document per user
    await db["conversation_history"].create_index("user_id", unique=True)
