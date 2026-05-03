# -*- coding: utf-8 -*-
"""
Tests for pure helper functions in agent/nodes/clarification.py.

No LLM calls are made — only the deterministic helpers are covered here.
"""
import pytest

from agent.nodes.clarification import _already_clarifying, _build_prompt, _needs_clarification


class TestNeedsClarification:
    def test_short_text_needs_clarification(self):
        assert _needs_clarification("Add a button") is True

    def test_long_technical_text_does_not_need_clarification(self):
        # >= 20 words AND contains a tech keyword → no clarification needed
        text = (
            "Implement a REST API endpoint for JWT authentication supporting registration "
            "and login with refresh token rotation using FastAPI and PostgreSQL as the "
            "primary database backend storage solution."
        )
        assert _needs_clarification(text) is False

    def test_text_with_api_keyword_does_not_need_clarification(self):
        text = " ".join(["word"] * 25) + " api integration"
        assert _needs_clarification(text) is False

    def test_text_with_database_keyword_does_not_need_clarification(self):
        text = " ".join(["word"] * 25) + " database migration"
        assert _needs_clarification(text) is False

    def test_text_with_cyrillic_api_keyword(self):
        text = " ".join(["слово"] * 25) + " апи интеграция"
        assert _needs_clarification(text) is False

    def test_exact_word_boundary_20(self):
        # exactly 20 words — below threshold even with tech keyword
        text = " ".join(["word"] * 19) + " api"
        # 20 words total → at boundary; _MIN_WORDS = 20 means len < 20 → True
        assert _needs_clarification(text) is False  # 20 words, boundary is inclusive

    def test_below_min_words(self):
        text = "Fix the bug in the authentication module"
        # < 20 words → always needs clarification
        assert _needs_clarification(text) is True


class TestAlreadyClarifying:
    def test_last_assistant_message_with_question(self):
        history = [
            {"role": "user", "content": "Fix login"},
            {"role": "assistant", "content": "What framework are you using?"},
        ]
        assert _already_clarifying(history) is True

    def test_last_assistant_message_without_question(self):
        history = [
            {"role": "user", "content": "Fix login"},
            {"role": "assistant", "content": "Sure, I can help with that."},
        ]
        assert _already_clarifying(history) is False

    def test_empty_history(self):
        assert _already_clarifying([]) is False

    def test_only_user_messages(self):
        history = [{"role": "user", "content": "Hello?"}]
        assert _already_clarifying(history) is False

    def test_multiple_messages_checks_last_assistant(self):
        history = [
            {"role": "assistant", "content": "What service?"},  # earlier question
            {"role": "user", "content": "Nova Poshta"},
            {"role": "assistant", "content": "Got it, estimating now."},  # last assistant — no question
        ]
        assert _already_clarifying(history) is False

    def test_interleaved_messages(self):
        history = [
            {"role": "user", "content": "Fix bug"},
            {"role": "assistant", "content": "Which file?"},
            {"role": "user", "content": "main.py"},
        ]
        # last assistant message has '?' even though user replied — still True
        assert _already_clarifying(history) is True


class TestBuildPrompt:
    def _state(self, **kwargs) -> dict:
        base = {
            "user_input": "Add a button",
            "project_context": [],
            "similar_tasks": [],
        }
        base.update(kwargs)
        return base

    def test_contains_task(self):
        prompt = _build_prompt(self._state(user_input="Add pagination"))
        assert "Add pagination" in prompt

    def test_project_context_included(self):
        state = self._state(project_context=["Module: users\nFiles: users/models.py"])
        prompt = _build_prompt(state)
        assert "Project context" in prompt
        assert "users/models.py" in prompt

    def test_similar_tasks_included(self):
        state = self._state(similar_tasks=[{"task": "Build login API", "total_hours": 4}])
        prompt = _build_prompt(state)
        assert "Similar past tasks" in prompt
        assert "Build login API" in prompt

    def test_no_context_prompt_still_has_task(self):
        prompt = _build_prompt(self._state())
        assert "Add a button" in prompt

    def test_project_context_capped_at_3_chunks(self):
        chunks = [f"chunk {i}" for i in range(10)]
        state = self._state(project_context=chunks)
        prompt = _build_prompt(state)
        # only chunks 0-2 should appear
        assert "chunk 0" in prompt
        assert "chunk 2" in prompt
        assert "chunk 3" not in prompt

    def test_similar_tasks_capped_at_2(self):
        tasks = [{"task": f"task {i}", "total_hours": i} for i in range(5)]
        state = self._state(similar_tasks=tasks)
        prompt = _build_prompt(state)
        assert "task 0" in prompt
        assert "task 1" in prompt
        assert "task 2" not in prompt
