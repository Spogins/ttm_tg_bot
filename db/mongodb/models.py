"""
Pydantic models for MongoDB documents: User, Project, and Estimation.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    # used as a default_factory so each instance gets its own timestamp (not a shared default)
    return datetime.now(timezone.utc)


class UserSettings(BaseModel):
    """
    Per-user preferences stored inside the User document.
    """
    language: str = "ru"
    experience_level: str = "mid"  # junior / mid / senior


class UserTokens(BaseModel):
    """
    Tracks daily and monthly LLM token consumption with rolling reset timestamps.
    """
    daily_used: int = 0
    daily_reset_at: datetime = Field(default_factory=utcnow)
    monthly_used: int = 0
    monthly_reset_at: datetime = Field(default_factory=utcnow)


class User(BaseModel):
    """
    Top-level user document stored in the 'users' collection.
    """
    user_id: int
    username: Optional[str] = None
    first_name: str
    active_project_id: Optional[str] = None
    settings: UserSettings = Field(default_factory=UserSettings)
    tokens: UserTokens = Field(default_factory=UserTokens)
    created_at: datetime = Field(default_factory=utcnow)


class Estimation(BaseModel):
    """
    Stored task estimation with hours, complexity, tech stack, and optional actuals.
    """
    estimation_id: str
    user_id: int
    project_id: Optional[str] = None
    project_name: str = ""
    task: str
    total_hours: float
    complexity: int  # 1–5
    tech_stack: list[str] = Field(default_factory=list)
    breakdown: dict = Field(default_factory=dict)
    actual_hours: Optional[float] = None
    created_at: datetime = Field(default_factory=utcnow)


class Project(BaseModel):
    """
    User project document with parsed tech stack and reference to its Qdrant collection.
    """
    project_id: str
    user_id: int
    name: str
    description: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    structure_raw: dict = Field(default_factory=dict)
    qdrant_collection: str = ""  # populated after indexing; empty means not yet indexed
    files_indexed: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
