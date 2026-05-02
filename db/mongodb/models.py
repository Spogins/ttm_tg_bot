# -*- coding: utf-8 -*-
"""
Pydantic models for MongoDB documents: User, Project, and Estimation.
"""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    """Return the current UTC datetime with timezone info."""
    # used as a default_factory so each instance gets its own timestamp (not a shared default)
    return datetime.now(timezone.utc)


def _as_utc(v: datetime) -> datetime:
    # MongoDB stores naive UTC datetimes; attach tzinfo so comparisons work
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


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

    @field_validator("daily_reset_at", "monthly_reset_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Attach UTC timezone to naive datetimes returned by MongoDB."""
        return _as_utc(v)


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

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Attach UTC timezone to naive datetimes returned by MongoDB."""
        return _as_utc(v)


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

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Attach UTC timezone to naive datetimes returned by MongoDB."""
        return _as_utc(v)


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

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Attach UTC timezone to naive datetimes returned by MongoDB."""
        return _as_utc(v)
