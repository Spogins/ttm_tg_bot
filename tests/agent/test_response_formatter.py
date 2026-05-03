# -*- coding: utf-8 -*-
import pytest

from agent.nodes.response_formatter import _format_clarification, _format_estimation, _format_sprint_plan


def _make_plan(project_name: str = "Test Project") -> dict:
    return {
        "project_name": project_name,
        "days": [
            {
                "day": 1,
                "tasks": [
                    {"name": "Task A", "hours": 5.0, "has_api_buffer": False, "complexity": 2, "confidence": "high"},
                    {"name": "Task B", "hours": 1.0, "has_api_buffer": False, "complexity": 1, "confidence": "medium"},
                ],
                "total_hours": 6.0,
            },
            {
                "day": 2,
                "tasks": [
                    {"name": "Task C", "hours": 7.2, "has_api_buffer": True, "complexity": 3, "confidence": "medium"},
                ],
                "total_hours": 7.2,
            },
        ],
        "total_hours": 13.2,
        "warnings": ["⚠️ «Task C» занимает 7.2 ч — больше одного дня"],
    }


class TestFormatSprintPlan:
    def test_contains_day_headers(self):
        text = _format_sprint_plan(_make_plan(), hours_per_day=6.0)
        assert "День 1" in text
        assert "День 2" in text

    def test_contains_task_names(self):
        text = _format_sprint_plan(_make_plan(), hours_per_day=6.0)
        assert "Task A" in text
        assert "Task C" in text

    def test_shows_api_buffer_marker(self):
        text = _format_sprint_plan(_make_plan(), hours_per_day=6.0)
        assert "API буфер" in text

    def test_shows_total_hours(self):
        text = _format_sprint_plan(_make_plan(), hours_per_day=6.0)
        assert "13.2" in text

    def test_shows_project_name(self):
        text = _format_sprint_plan(_make_plan("My Project"), hours_per_day=6.0)
        assert "My Project" in text

    def test_no_project_name_omits_dash(self):
        text = _format_sprint_plan(_make_plan(""), hours_per_day=6.0)
        assert "Sprint Plan —" not in text

    def test_shows_warnings(self):
        text = _format_sprint_plan(_make_plan(), hours_per_day=6.0)
        assert "больше одного дня" in text

    def test_none_plan_returns_error(self):
        text = _format_sprint_plan(None, hours_per_day=6.0)
        assert "❌" in text


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_estimation(complexity: int = 3, confidence: str = "medium") -> dict:
    return {
        "subtasks": [{"name": "Task A", "hours": 3.0}, {"name": "Task B", "hours": 2.0}],
        "total_hours": 5.0,
        "complexity": complexity,
        "confidence": confidence,
    }


def _state(estimation=None, risks=None, similar=None, question=None) -> dict:
    return {
        "estimation": estimation,
        "risks": risks or [],
        "similar_tasks": similar or [],
        "clarification_question": question or "",
    }


# ── _format_estimation ────────────────────────────────────────────────────────


class TestFormatEstimation:
    def test_none_estimation_returns_error(self):
        assert "❌" in _format_estimation(_state())

    def test_shows_subtask_names(self):
        text = _format_estimation(_state(_make_estimation()))
        assert "Task A" in text
        assert "Task B" in text

    def test_shows_total_hours(self):
        text = _format_estimation(_state(_make_estimation()))
        assert "5.0h" in text

    def test_complexity_3_shows_medium(self):
        text = _format_estimation(_state(_make_estimation(complexity=3)))
        assert "Medium" in text

    def test_complexity_1_shows_trivial(self):
        text = _format_estimation(_state(_make_estimation(complexity=1)))
        assert "Trivial" in text

    def test_complexity_5_shows_very_hard(self):
        text = _format_estimation(_state(_make_estimation(complexity=5)))
        assert "Very hard" in text

    def test_unknown_complexity_falls_back_to_raw_int(self):
        est = {**_make_estimation(), "complexity": 7}
        text = _format_estimation(_state(est))
        assert "7" in text

    def test_high_confidence_emoji(self):
        text = _format_estimation(_state(_make_estimation(confidence="high")))
        assert "🟢" in text

    def test_medium_confidence_emoji(self):
        text = _format_estimation(_state(_make_estimation(confidence="medium")))
        assert "🟡" in text

    def test_low_confidence_emoji(self):
        text = _format_estimation(_state(_make_estimation(confidence="low")))
        assert "🔴" in text

    def test_unknown_confidence_no_emoji(self):
        est = {**_make_estimation(), "confidence": "extreme"}
        text = _format_estimation(_state(est))
        assert "🟢" not in text and "🟡" not in text and "🔴" not in text

    def test_risks_section_present_when_non_empty(self):
        text = _format_estimation(_state(_make_estimation(), risks=["Data loss risk"]))
        assert "Риски" in text
        assert "Data loss risk" in text

    def test_risks_section_absent_when_empty(self):
        text = _format_estimation(_state(_make_estimation()))
        assert "Риски" not in text

    def test_similar_tasks_section_present(self):
        similar = [{"task": "Similar bug fix", "total_hours": 4.0}]
        text = _format_estimation(_state(_make_estimation(), similar=similar))
        assert "Similar bug fix" in text
        assert "Похожие задачи" in text

    def test_similar_tasks_absent_when_empty(self):
        text = _format_estimation(_state(_make_estimation()))
        assert "Похожие задачи" not in text


# ── _format_clarification ─────────────────────────────────────────────────────


class TestFormatClarification:
    def test_returns_question_text(self):
        text = _format_clarification(_state(question="What is the scope?"))
        assert "What is the scope?" in text

    def test_contains_emoji(self):
        text = _format_clarification(_state(question="Scope?"))
        assert "🤔" in text

    def test_default_text_when_key_missing(self):
        # clarification_question key absent → .get() returns the default literal
        text = _format_clarification({})
        assert "Опишите задачу подробнее" in text
