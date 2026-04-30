from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSettings(BaseModel):
    language: str = "ru"
    experience_level: str = "mid"  # junior / mid / senior


class UserTokens(BaseModel):
    daily_used: int = 0
    daily_reset_at: datetime = Field(default_factory=utcnow)
    monthly_used: int = 0
    monthly_reset_at: datetime = Field(default_factory=utcnow)


class User(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: str
    active_project_id: Optional[str] = None
    settings: UserSettings = Field(default_factory=UserSettings)
    tokens: UserTokens = Field(default_factory=UserTokens)
    created_at: datetime = Field(default_factory=utcnow)


class Project(BaseModel):
    project_id: str
    user_id: int
    name: str
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    structure_raw: dict = Field(default_factory=dict)
    qdrant_collection: str = ""
    files_indexed: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
