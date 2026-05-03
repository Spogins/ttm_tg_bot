# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from db.mongodb.models import Estimation, Project, Sprint, User, UserTokens, _as_utc


class TestAsUtc:
    def test_naive_datetime_gets_utc(self):
        naive = datetime(2026, 4, 25, 12, 0, 0)
        result = _as_utc(naive)
        assert result.tzinfo == timezone.utc

    def test_aware_datetime_returned_unchanged(self):
        aware = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)
        assert _as_utc(aware) == aware

    def test_preserves_date_and_time_values(self):
        naive = datetime(2026, 4, 25, 15, 30, 0)
        result = _as_utc(naive)
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 25
        assert result.hour == 15


class TestUserTokensValidator:
    def test_naive_daily_reset_at_gets_utc(self):
        tokens = UserTokens(
            daily_reset_at=datetime(2026, 1, 1),
            monthly_reset_at=datetime(2026, 1, 1),
        )
        assert tokens.daily_reset_at.tzinfo == timezone.utc

    def test_naive_monthly_reset_at_gets_utc(self):
        tokens = UserTokens(
            daily_reset_at=datetime(2026, 1, 1),
            monthly_reset_at=datetime(2026, 1, 1),
        )
        assert tokens.monthly_reset_at.tzinfo == timezone.utc

    def test_defaults_to_zero_usage(self):
        tokens = UserTokens()
        assert tokens.daily_used == 0
        assert tokens.monthly_used == 0


class TestUserModel:
    def test_basic_construction(self):
        user = User(user_id=42, first_name="Bogdan")
        assert user.user_id == 42
        assert user.first_name == "Bogdan"

    def test_optional_fields_default_to_none(self):
        user = User(user_id=1, first_name="A")
        assert user.username is None
        assert user.active_project_id is None

    def test_naive_created_at_gets_utc(self):
        user = User(user_id=1, first_name="A", created_at=datetime(2026, 1, 1))
        assert user.created_at.tzinfo == timezone.utc

    def test_settings_defaults(self):
        user = User(user_id=1, first_name="A")
        assert user.settings.language == "ru"
        assert user.settings.experience_level == "mid"


class TestEstimationModel:
    def _make(self, **kwargs) -> Estimation:
        defaults = dict(estimation_id="e1", user_id=1, task="Fix bug", total_hours=4.0, complexity=2)
        return Estimation(**{**defaults, **kwargs})

    def test_optional_fields_default(self):
        est = self._make()
        assert est.actual_hours is None
        assert est.reminder_at is None
        assert est.tech_stack == []
        assert est.breakdown == {}

    def test_project_name_defaults_to_empty(self):
        assert self._make().project_name == ""

    def test_none_reminder_at_passes_validator(self):
        est = self._make(reminder_at=None)
        assert est.reminder_at is None

    def test_naive_created_at_gets_utc(self):
        est = self._make(created_at=datetime(2026, 1, 1))
        assert est.created_at.tzinfo == timezone.utc

    def test_naive_reminder_at_gets_utc(self):
        est = self._make(reminder_at=datetime(2026, 1, 1))
        assert est.reminder_at.tzinfo == timezone.utc


class TestProjectModel:
    def test_basic_construction(self):
        p = Project(project_id="p1", user_id=1, name="CRM")
        assert p.name == "CRM"

    def test_qdrant_collection_defaults_to_empty(self):
        p = Project(project_id="p1", user_id=1, name="CRM")
        assert p.qdrant_collection == ""

    def test_files_indexed_defaults_to_zero(self):
        p = Project(project_id="p1", user_id=1, name="CRM")
        assert p.files_indexed == 0

    def test_naive_created_at_gets_utc(self):
        p = Project(project_id="p1", user_id=1, name="CRM", created_at=datetime(2026, 1, 1))
        assert p.created_at.tzinfo == timezone.utc


class TestSprintModel:
    def test_basic_construction(self):
        s = Sprint(
            sprint_id="s1",
            user_id=1,
            hours_per_day=6.0,
            tasks_input=["Task A", "Task B"],
            days=[],
            total_hours=0.0,
        )
        assert s.sprint_id == "s1"
        assert s.hours_per_day == 6.0

    def test_warnings_defaults_to_empty_list(self):
        s = Sprint(sprint_id="s1", user_id=1, hours_per_day=6.0, tasks_input=[], days=[], total_hours=0.0)
        assert s.warnings == []

    def test_project_name_defaults_to_empty(self):
        s = Sprint(sprint_id="s1", user_id=1, hours_per_day=6.0, tasks_input=[], days=[], total_hours=0.0)
        assert s.project_name == ""

    def test_naive_created_at_gets_utc(self):
        s = Sprint(
            sprint_id="s1",
            user_id=1,
            hours_per_day=6.0,
            tasks_input=[],
            days=[],
            total_hours=0.0,
            created_at=datetime(2026, 1, 1),
        )
        assert s.created_at.tzinfo == timezone.utc
