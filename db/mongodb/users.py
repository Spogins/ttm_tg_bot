# -*- coding: utf-8 -*-
"""
CRUD helpers and token-limit logic for the 'users' collection.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.mongodb.client import get_database
from db.mongodb.models import User


async def get_user(user_id: int) -> Optional[User]:
    """
    Fetch a user by Telegram ID, returning None if not found.

    :param user_id: Telegram user ID.
    :return: User instance or None.
    """
    db = get_database()
    doc = await db["users"].find_one({"user_id": user_id})
    return User(**doc) if doc else None


async def get_or_create_user(user_id: int, first_name: str, username: Optional[str] = None) -> User:
    """
    Return an existing user or insert and return a new one.

    :param user_id: Telegram user ID.
    :param first_name: User's first name from Telegram.
    :param username: Optional Telegram username.
    :return: Existing or newly created User instance.
    """
    user = await get_user(user_id)
    if user:
        return user
    user = User(user_id=user_id, first_name=first_name, username=username)
    await get_database()["users"].insert_one(user.model_dump())
    return user


async def set_active_project(user_id: int, project_id: Optional[str]) -> None:
    """
    Update the user's active_project_id (pass None to clear it).

    :param user_id: Telegram user ID.
    :param project_id: Project UUID to set as active, or None to clear.
    :return: None
    """
    await get_database()["users"].update_one(
        {"user_id": user_id},
        {"$set": {"active_project_id": project_id}},
    )


async def increment_tokens(user_id: int, amount: int) -> None:
    """
    Add token usage, resetting daily or monthly counters if their windows have expired.

    :param user_id: Telegram user ID.
    :param amount: Number of tokens to add.
    :return: None
    """
    db = get_database()
    now = datetime.now(timezone.utc)
    user = await get_user(user_id)
    if not user:
        return

    daily_expired = now >= user.tokens.daily_reset_at + timedelta(days=1)
    monthly_expired = now >= user.tokens.monthly_reset_at + timedelta(days=30)

    # A field must appear in exactly one operator — never in both $inc and $set.
    # When the window has expired we $set (reset to amount); otherwise we $inc.
    set_fields: dict = {}
    inc_fields: dict = {}

    if daily_expired:
        set_fields["tokens.daily_used"] = amount
        set_fields["tokens.daily_reset_at"] = now
    else:
        inc_fields["tokens.daily_used"] = amount

    if monthly_expired:
        set_fields["tokens.monthly_used"] = amount
        set_fields["tokens.monthly_reset_at"] = now
    else:
        inc_fields["tokens.monthly_used"] = amount

    update: dict = {}
    if inc_fields:
        update["$inc"] = inc_fields
    if set_fields:
        update["$set"] = set_fields

    await db["users"].update_one({"user_id": user_id}, update)


async def check_token_limits(user_id: int, daily_limit: int, monthly_limit: int) -> tuple[bool, str]:
    """
    Return (allowed, reason_message) based on current daily and monthly usage.

    :param user_id: Telegram user ID.
    :param daily_limit: Maximum tokens allowed per day.
    :param monthly_limit: Maximum tokens allowed per month.
    :return: Tuple of (is_allowed, human-readable reason if blocked).
    """
    user = await get_user(user_id)
    if not user:
        return True, ""
    if user.tokens.daily_used >= daily_limit:
        return False, f"Дневной лимит токенов исчерпан ({daily_limit:,}). Попробуйте завтра."  # noqa: E231
    if user.tokens.monthly_used >= monthly_limit:
        return False, f"Месячный лимит токенов исчерпан ({monthly_limit:,})."  # noqa: E231
    return True, ""
