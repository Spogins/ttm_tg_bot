# -*- coding: utf-8 -*-
description = "backfill scope/estimation_mode/status on existing estimations and add status index"

import pymongo


async def up(db):
    """
    Backfill scope, estimation_mode, and status on pre-existing estimations; add status index.

    :param db: AsyncIOMotorDatabase instance.
    :return: None
    """
    # backfill documents that predate the new fields
    await db["estimations"].update_many(
        {"scope": {"$exists": False}},
        {"$set": {"scope": []}},
    )
    await db["estimations"].update_many(
        {"estimation_mode": {"$exists": False}},
        {"$set": {"estimation_mode": "realistic"}},
    )
    # existing docs with actual_hours recorded are implicitly "done"
    await db["estimations"].update_many(
        {"status": {"$exists": False}, "actual_hours": {"$ne": None}},
        {"$set": {"status": "done"}},
    )
    await db["estimations"].update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "in_progress"}},
    )

    # index for filtering/sorting history by status
    await db["estimations"].create_index(
        [("user_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)],
    )
