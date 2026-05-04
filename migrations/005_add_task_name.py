# -*- coding: utf-8 -*-
description = "backfill task_name on existing estimations"


async def up(db):
    await db["estimations"].update_many(
        {"task_name": {"$exists": False}},
        {"$set": {"task_name": ""}},
    )
