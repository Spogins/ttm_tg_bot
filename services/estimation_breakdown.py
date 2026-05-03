# -*- coding: utf-8 -*-
"""Breakdown logic: categorize agent subtasks, apply estimation mode multiplier, and calculate totals."""

CATEGORY_NAMES: dict[str, str] = {
    "implementation": "Реализация",
    "tests": "Тесты",
    "bugfix": "Багфикс",
    "code_review": "Code Review",
    "documentation": "Документация",
}

MULTIPLIERS: dict[str, float] = {
    "optimistic": 0.8,
    "realistic": 1.0,
    "pessimistic": 1.3,
}

_VARIABLE = {"implementation", "tests", "bugfix"}

DEFAULT_TOGGLES: dict[str, bool] = {
    "implementation": True,
    "tests": True,
    "bugfix": True,
    "code_review": True,
    "documentation": False,
}

_TEST_KEYWORDS = {"тест", "test", "qa", "spec", "проверк"}


def categorize_subtasks(subtasks: list[dict]) -> dict[str, float]:
    """
    Split agent subtasks into implementation/tests; add fixed bugfix/code_review/documentation.

    Bugfix = 10% of implementation hours. Code review and documentation are fixed at 0.5h each.
    """
    impl = 0.0
    tests = 0.0
    for s in subtasks:
        if any(kw in s["name"].lower() for kw in _TEST_KEYWORDS):
            tests += s["hours"]
        else:
            impl += s["hours"]
    return {
        "implementation": round(impl, 1),
        "tests": round(tests, 1),
        "bugfix": round(impl * 0.1, 1),
        "code_review": 0.5,
        "documentation": 0.5,
    }


def apply_mode(breakdown: dict[str, float], mode: str) -> dict[str, float]:
    """Scale variable categories by the mode multiplier; fixed categories are unchanged."""
    m = MULTIPLIERS.get(mode, 1.0)
    return {cat: round(hours * m, 1) if cat in _VARIABLE else hours for cat, hours in breakdown.items()}


def calculate_total(breakdown: dict[str, float], toggles: dict[str, bool]) -> float:
    """Sum hours for all enabled categories."""
    return round(sum(h for cat, h in breakdown.items() if toggles.get(cat, True)), 1)
