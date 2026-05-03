# -*- coding: utf-8 -*-
from agent.graph.graph import _route_clarification, _route_intent


class TestRouteIntent:
    def test_sprint_tasks_present_returns_sprint_planner(self):
        assert _route_intent({"sprint_tasks": ["Task A"], "intent": "unknown"}) == "sprint_planner"

    def test_sprint_tasks_overrides_estimate_intent(self):
        assert _route_intent({"sprint_tasks": ["Task A"], "intent": "estimate"}) == "sprint_planner"

    def test_estimate_intent_returns_project_context(self):
        assert _route_intent({"sprint_tasks": None, "intent": "estimate"}) == "project_context"

    def test_project_add_returns_project_manager(self):
        assert _route_intent({"sprint_tasks": None, "intent": "project_add"}) == "project_manager"

    def test_project_switch_returns_project_manager(self):
        assert _route_intent({"sprint_tasks": None, "intent": "project_switch"}) == "project_manager"

    def test_sprint_intent_without_tasks_returns_sprint_planner(self):
        assert _route_intent({"sprint_tasks": None, "intent": "sprint"}) == "sprint_planner"

    def test_unknown_intent_returns_fallback(self):
        assert _route_intent({"sprint_tasks": None, "intent": "unknown"}) == "fallback"

    def test_missing_intent_defaults_to_fallback(self):
        assert _route_intent({"sprint_tasks": None}) == "fallback"

    def test_empty_sprint_tasks_list_bypasses_sprint(self):
        # empty list is falsy — should not route to sprint_planner
        assert _route_intent({"sprint_tasks": [], "intent": "estimate"}) == "project_context"


class TestRouteClarification:
    def test_clarification_needed_routes_to_formatter(self):
        assert _route_clarification({"clarification_needed": True}) == "response_formatter"

    def test_no_clarification_routes_to_estimation(self):
        assert _route_clarification({"clarification_needed": False}) == "estimation"

    def test_missing_key_routes_to_estimation(self):
        assert _route_clarification({}) == "estimation"
