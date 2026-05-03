# -*- coding: utf-8 -*-
from services.estimation_breakdown import DEFAULT_TOGGLES, apply_mode, calculate_total, categorize_subtasks


class TestCategorizeSubtasks:
    def test_test_keyword_goes_to_tests_bucket(self):
        subtasks = [
            {"name": "Backend: написать тесты для endpoint", "hours": 1.5},
            {"name": "Backend: реализовать endpoint", "hours": 3.0},
        ]
        result = categorize_subtasks(subtasks)
        assert result["tests"] == 1.5
        assert result["implementation"] == 3.0

    def test_english_test_keyword(self):
        result = categorize_subtasks([{"name": "Write unit tests", "hours": 2.0}])
        assert result["tests"] == 2.0
        assert result["implementation"] == 0.0

    def test_bugfix_is_10_percent_of_implementation(self):
        result = categorize_subtasks([{"name": "Implement feature", "hours": 10.0}])
        assert result["bugfix"] == 1.0

    def test_fixed_code_review_and_docs(self):
        result = categorize_subtasks([{"name": "Implement", "hours": 4.0}])
        assert result["code_review"] == 0.5
        assert result["documentation"] == 0.5

    def test_empty_subtasks(self):
        result = categorize_subtasks([])
        assert result["implementation"] == 0.0
        assert result["tests"] == 0.0
        assert result["bugfix"] == 0.0


class TestApplyMode:
    def _bd(self):
        return {"implementation": 10.0, "tests": 2.0, "bugfix": 1.0, "code_review": 0.5, "documentation": 0.5}

    def test_realistic_is_identity(self):
        result = apply_mode(self._bd(), "realistic")
        assert result["implementation"] == 10.0
        assert result["tests"] == 2.0
        assert result["code_review"] == 0.5  # fixed, not scaled

    def test_optimistic_scales_variable(self):
        result = apply_mode(self._bd(), "optimistic")
        assert result["implementation"] == 8.0
        assert result["bugfix"] == 0.8
        assert result["code_review"] == 0.5  # unchanged

    def test_pessimistic_scales_variable(self):
        result = apply_mode(self._bd(), "pessimistic")
        assert result["implementation"] == 13.0
        assert result["code_review"] == 0.5  # unchanged

    def test_unknown_mode_defaults_to_realistic(self):
        result = apply_mode(self._bd(), "unknown")
        assert result["implementation"] == 10.0


class TestCalculateTotal:
    def _bd(self):
        return {"implementation": 8.0, "tests": 2.0, "bugfix": 1.0, "code_review": 0.5, "documentation": 0.5}

    def test_sums_only_enabled(self):
        toggles = {"implementation": True, "tests": True, "bugfix": False, "code_review": True, "documentation": False}
        assert calculate_total(self._bd(), toggles) == 10.5

    def test_all_enabled(self):
        assert calculate_total(self._bd(), {k: True for k in self._bd()}) == 12.0

    def test_default_toggles_excludes_documentation(self):
        # DEFAULT_TOGGLES has documentation=False
        assert calculate_total(self._bd(), DEFAULT_TOGGLES) == 11.5
