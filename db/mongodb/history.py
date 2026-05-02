# -*- coding: utf-8 -*-
"""
CRUD helpers for per-user conversation history stored in the 'conversation_history' collection.
"""
from datetime import datetime, timezone

from db.mongodb.client import get_database

# number of messages kept per user; older messages are dropped automatically
_HISTORY_LIMIT = 10


async def get_history(user_id: int) -> list[dict]:
    """
    Return the stored conversation messages for a user, oldest first.

    :param user_id: Telegram user ID.
    :return: List of message dicts with 'role' and 'content' keys.
    """
    db = get_database()
    doc = await db["conversation_history"].find_one({"user_id": user_id})
    return doc["messages"] if doc else []


async def append_messages(user_id: int, messages: list[dict]) -> None:
    """
    Push new messages and trim the list to the last _HISTORY_LIMIT entries.

    :param user_id: Telegram user ID.
    :param messages: List of message dicts to append (role + content).
    :return: None
    """
    db = get_database()
    await db["conversation_history"].update_one(
        {"user_id": user_id},
        {
            "$push": {
                "messages": {
                    # $each appends all items; $slice keeps only the last N
                    "$each": messages,
                    "$slice": -_HISTORY_LIMIT,
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=True,  # create document on first message
    )


async def clear_history(user_id: int) -> None:
    """
    Delete the conversation history document for a user.

    :param user_id: Telegram user ID.
    :return: None
    """
    await get_database()["conversation_history"].delete_one({"user_id": user_id})
