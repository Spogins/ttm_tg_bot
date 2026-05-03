# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from bot.handlers.common import _fmt_date, _format_history
from db.mongodb.models import Estimation


def _make_estimation(task: str, total_hours: float, actual_hours=None, month: int = 4, day: int = 25) -> Estimation:
    return Estimation(
        estimation_id="test-id",
        user_id=1,
        task=task,
        total_hours=total_hours,
        complexity=2,
        actual_hours=actual_hours,
        created_at=datetime(2026, month, day, tzinfo=timezone.utc),
    )


class TestFmtDate:
    def test_april(self):
        assert _fmt_date(datetime(2026, 4, 25, tzinfo=timezone.utc)) == "25 апр"

    def test_may(self):
        assert _fmt_date(datetime(2026, 5, 3, tzinfo=timezone.utc)) == "3 май"

    def test_january(self):
        assert _fmt_date(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "1 янв"


class TestFormatHistory:
    def test_empty_list_shows_placeholder(self):
        text = _format_history([])
        assert "Нет сохранённых оценок" in text

    def test_header_without_project(self):
        text = _format_history([])
        assert "📋 История оценок</b>" in text

    def test_header_with_project(self):
        text = _format_history([], project_name="CRM Instagram")
        assert "CRM Instagram" in text

    def test_row_shows_estimated_hours(self):
        est = _make_estimation("Fix bug", 5.5)
        text = _format_history([est])
        assert "5.5 ч" in text

    def test_row_shows_actual_hours_when_present(self):
        est = _make_estimation("Fix bug", 5.5, actual_hours=7.0)
        text = _format_history([est])
        assert "7.0 ч реально" in text

    def test_row_shows_dash_when_no_actual(self):
        est = _make_estimation("Fix bug", 5.5)
        text = _format_history([est])
        assert "→  —" in text

    def test_row_contains_date(self):
        est = _make_estimation("Fix bug", 5.5, month=4, day=23)
        text = _format_history([est])
        assert "23 апр" in text

    def test_numbering_starts_at_one(self):
        est = _make_estimation("Task", 3.0)
        text = _format_history([est])
        assert "1. " in text

    def test_multiple_rows_numbered(self):
        ests = [_make_estimation(f"Task {i}", float(i)) for i in range(1, 4)]
        text = _format_history(ests)
        assert "1. " in text
        assert "2. " in text
        assert "3. " in text

    def test_long_task_name_truncated(self):
        long_task = "A" * 60
        est = _make_estimation(long_task, 3.0)
        text = _format_history([est])
        assert "…" in text
        assert "A" * 60 not in text
