# -*- coding: utf-8 -*-
from datetime import date

from services.sprint_exporter import _format_date_ru, generate_sprint_markdown


def _make_plan(project_name: str = "My Project") -> dict:
    return {
        "project_name": project_name,
        "days": [
            {
                "day": 1,
                "tasks": [
                    {"name": "Task A", "hours": 5.0, "has_api_buffer": False},
                    {"name": "Task B", "hours": 1.0, "has_api_buffer": False},
                ],
                "total_hours": 6.0,
            },
            {
                "day": 2,
                "tasks": [
                    {"name": "Nova Poshta", "hours": 7.2, "has_api_buffer": True},
                ],
                "total_hours": 7.2,
            },
        ],
        "total_hours": 13.2,
        "warnings": ["⚠️ «Nova Poshta» занимает 7.2 ч — больше одного дня"],
    }


class TestFormatDateRu:
    def test_april(self):
        assert _format_date_ru(date(2026, 4, 25)) == "25 апр"

    def test_may(self):
        assert _format_date_ru(date(2026, 5, 8)) == "8 май"

    def test_january(self):
        assert _format_date_ru(date(2026, 1, 1)) == "1 янв"

    def test_december(self):
        assert _format_date_ru(date(2026, 12, 31)) == "31 дек"


class TestGenerateSprintMarkdown:
    def test_contains_project_name(self):
        md = generate_sprint_markdown(_make_plan("CRM"), 6.0, date(2026, 4, 25))
        assert "CRM" in md

    def test_header_without_project_name(self):
        md = generate_sprint_markdown(_make_plan(""), 6.0, date(2026, 4, 25))
        assert "# Sprint Plan\n" in md
        assert "Sprint Plan —" not in md

    def test_contains_day_headers(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "## День 1" in md
        assert "## День 2" in md

    def test_contains_task_names(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "Task A" in md
        assert "Nova Poshta" in md

    def test_tasks_use_checkbox_format(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "- [ ] Task A" in md

    def test_api_buffer_note_present(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "API буфер" in md

    def test_no_api_buffer_note_when_false(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "- [ ] Task A — 5.0ч\n" in md

    def test_total_hours_in_summary(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "13.2" in md

    def test_capacity_in_header(self):
        md = generate_sprint_markdown(_make_plan(), 6.5, date(2026, 4, 25))
        assert "6.5 ч/день" in md

    def test_period_dates(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "25 апр" in md
        assert "26 апр" in md  # day 2

    def test_warnings_present(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "больше одного дня" in md

    def test_warnings_as_blockquote(self):
        md = generate_sprint_markdown(_make_plan(), 6.0, date(2026, 4, 25))
        assert "> ⚠️" in md

    def test_empty_plan_no_crash(self):
        plan = {"project_name": "", "days": [], "total_hours": 0, "warnings": []}
        md = generate_sprint_markdown(plan, 8.0, date(2026, 4, 25))
        assert "Итого: 0 часов / 0 дней" in md
