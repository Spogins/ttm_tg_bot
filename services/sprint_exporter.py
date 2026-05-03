# -*- coding: utf-8 -*-
"""
Pure-function Markdown generator for sprint plans.
"""
from datetime import date, timedelta

_MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def _format_date_ru(d: date) -> str:
    """Return a short Russian date string like '25 апр'."""
    return f"{d.day} {_MONTHS_RU[d.month - 1]}"


def generate_sprint_markdown(
    sprint_plan: dict,
    hours_per_day: float,
    start_date: date | None = None,
) -> str:
    """
    Render a sprint plan as a Markdown document suitable for download.

    :param sprint_plan: SprintPlan dict produced by sprint_planner_node.
    :param hours_per_day: Daily capacity in hours (shown in the header).
    :param start_date: First day of the sprint; defaults to today.
    :return: UTF-8 Markdown string.
    """
    if start_date is None:
        start_date = date.today()

    project_name = sprint_plan.get("project_name", "")
    header = "# Sprint Plan"
    if project_name:
        header += f" — {project_name}"

    days = sprint_plan.get("days", [])
    n_days = len(days)
    end_date = start_date + timedelta(days=max(n_days - 1, 0))

    lines = [
        header,
        f"**Период:** {_format_date_ru(start_date)} — {_format_date_ru(end_date)}",
        f"**Capacity:** {hours_per_day} ч/день",  # noqa: E231
        "",
    ]

    for i, day in enumerate(days):
        day_date = start_date + timedelta(days=i)
        lines.append(f"## День {day['day']} ({_format_date_ru(day_date)})")
        for task in day["tasks"]:
            buffer_note = "  _(+20% API буфер)_" if task.get("has_api_buffer") else ""
            lines.append(f"- [ ] {task['name']} — {task['hours']}ч{buffer_note}")  # noqa: E201
        lines.append("")

    lines.append(f"## Итого: {sprint_plan.get('total_hours', 0)} часов / {n_days} дней")

    warnings = sprint_plan.get("warnings", [])
    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"> {w}")

    return "\n".join(lines)
