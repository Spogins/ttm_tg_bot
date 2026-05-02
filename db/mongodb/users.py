"""
CRUD helpers and token-limit logic for the 'users' collection.
"""
from datetime import datetime, timezone, timedelta
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

    # base update always increments both counters
    update: dict = {"$inc": {"tokens.daily_used": amount, "tokens.monthly_used": amount}}

    if now >= user.tokens.daily_reset_at + timedelta(days=1):
        # window expired: replace $inc with $set to reset the counter to the new amount
        update["$set"] = {
            "tokens.daily_used": amount,
            "tokens.daily_reset_at": now,
        }

    if now >= user.tokens.monthly_reset_at + timedelta(days=30):
        monthly_set = {"tokens.monthly_used": amount, "tokens.monthly_reset_at": now}
        # merge into existing $set (if daily reset already created it) without clobbering it
        update.setdefault("$set", {}).update(monthly_set)

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
        return False, f"Дневной лимит токенов исчерпан ({daily_limit:,}). Попробуйте завтра."
    if user.tokens.monthly_used >= monthly_limit:
        return False, f"Месячный лимит токенов исчерпан ({monthly_limit:,})."
    return True, ""
