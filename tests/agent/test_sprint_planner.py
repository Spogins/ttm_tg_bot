# -*- coding: utf-8 -*-
import pytest

from agent.nodes.sprint_planner import _build_warnings, _has_api_keywords, _pack_into_days


class TestHasApiKeywords:
    def test_detects_api_in_task_name(self):
        assert _has_api_keywords("Nova Poshta integration", []) is True

    def test_detects_api_in_subtask(self):
        assert _has_api_keywords("Order filter", ["Call external API", "Save result"]) is True

    def test_no_keywords(self):
        assert _has_api_keywords("Admin dashboard", ["Build UI", "Write tests"]) is False

    def test_case_insensitive(self):
        assert _has_api_keywords("Stripe WEBHOOK handler", []) is True

    def test_monobank_keyword(self):
        assert _has_api_keywords("Monobank payment", []) is True

    def test_no_false_positive_substring(self):
        assert _has_api_keywords("stripes pattern", []) is False

    def test_no_false_positive_telegram_like(self):
        assert _has_api_keywords("telegramic", []) is False


class TestPackIntoDays:
    def _task(self, name: str, hours: float) -> dict:
        return {
            "name": name,
            "hours": hours,
            "has_api_buffer": False,
            "complexity": 2,
            "confidence": "medium",
        }

    def test_single_task_fits_in_one_day(self):
        tasks = [self._task("Task A", 4.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        assert len(days) == 1
        assert days[0]["total_hours"] == 4.0

    def test_two_tasks_fit_in_one_day(self):
        tasks = [self._task("A", 3.0), self._task("B", 2.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        assert len(days) == 1
        assert days[0]["total_hours"] == 5.0

    def test_overflow_creates_second_day(self):
        tasks = [self._task("A", 4.0), self._task("B", 4.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        assert len(days) == 2

    def test_largest_task_first(self):
        tasks = [self._task("Small", 1.0), self._task("Big", 5.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        assert days[0]["tasks"][0]["name"] == "Big"

    def test_oversized_task_gets_own_day(self):
        tasks = [self._task("Huge", 10.0), self._task("Small", 2.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        huge_day = next(d for d in days if d["tasks"][0]["name"] == "Huge")
        assert len(huge_day["tasks"]) == 1

    def test_days_are_numbered_from_one(self):
        tasks = [self._task("A", 4.0), self._task("B", 4.0)]
        days = _pack_into_days(tasks, hours_per_day=6.0)
        assert days[0]["day"] == 1
        assert days[1]["day"] == 2

    def test_empty_tasks_returns_empty(self):
        assert _pack_into_days([], hours_per_day=8.0) == []


class TestBuildWarnings:
    def _task(self, name: str, hours: float, confidence: str = "medium", complexity: int = 3) -> dict:
        return {
            "name": name,
            "hours": hours,
            "has_api_buffer": False,
            "complexity": complexity,
            "confidence": confidence,
        }

    def test_oversized_task_warning(self):
        tasks = [self._task("Big task", 10.0)]
        warnings = _build_warnings(tasks, hours_per_day=6.0)
        assert any("больше одного дня" in w for w in warnings)

    def test_low_confidence_warning(self):
        tasks = [self._task("Vague task", 3.0, confidence="low")]
        warnings = _build_warnings(tasks, hours_per_day=6.0)
        assert any("низкая уверенность" in w for w in warnings)

    def test_complexity_5_warning(self):
        tasks = [self._task("Hard task", 5.0, complexity=5)]
        warnings = _build_warnings(tasks, hours_per_day=6.0)
        assert any("высокая сложность" in w for w in warnings)

    def test_no_warnings_for_normal_task(self):
        tasks = [self._task("Normal", 3.0)]
        warnings = _build_warnings(tasks, hours_per_day=8.0)
        assert warnings == []
