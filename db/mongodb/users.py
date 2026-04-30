from datetime import datetime, timezone, timedelta
from typing import Optional

from db.mongodb.client import get_database
from db.mongodb.models import User


async def get_user(user_id: int) -> Optional[User]:
    db = get_database()
    doc = await db["users"].find_one({"user_id": user_id})
    return User(**doc) if doc else None


async def get_or_create_user(user_id: int, first_name: str, username: Optional[str] = None) -> User:
    user = await get_user(user_id)
    if user:
        return user
    user = User(user_id=user_id, first_name=first_name, username=username)
    await get_database()["users"].insert_one(user.model_dump())
    return user


async def set_active_project(user_id: int, project_id: Optional[str]) -> None:
    await get_database()["users"].update_one(
        {"user_id": user_id},
        {"$set": {"active_project_id": project_id}},
    )


async def increment_tokens(user_id: int, amount: int) -> None:
    db = get_database()
    now = datetime.now(timezone.utc)
    user = await get_user(user_id)
    if not user:
        return

    update: dict = {"$inc": {"tokens.daily_used": amount, "tokens.monthly_used": amount}}

    if now >= user.tokens.daily_reset_at + timedelta(days=1):
        update["$set"] = {
            "tokens.daily_used": amount,
            "tokens.daily_reset_at": now,
        }

    if now >= user.tokens.monthly_reset_at + timedelta(days=30):
        monthly_set = {"tokens.monthly_used": amount, "tokens.monthly_reset_at": now}
        update.setdefault("$set", {}).update(monthly_set)

    await db["users"].update_one({"user_id": user_id}, update)


async def check_token_limits(user_id: int, daily_limit: int, monthly_limit: int) -> tuple[bool, str]:
    user = await get_user(user_id)
    if not user:
        return True, ""
    if user.tokens.daily_used >= daily_limit:
        return False, f"Дневной лимит токенов исчерпан ({daily_limit:,}). Попробуйте завтра."
    if user.tokens.monthly_used >= monthly_limit:
        return False, f"Месячный лимит токенов исчерпан ({monthly_limit:,})."
    return True, ""
