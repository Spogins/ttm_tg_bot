# -*- coding: utf-8 -*-
import pytest

from agent.nodes.input_processor import input_processor


class TestInputProcessor:
    async def test_trims_leading_trailing_whitespace(self):
        result = await input_processor({"user_input": "  hello  "})
        assert result["user_input"] == "hello"

    async def test_collapses_multiple_spaces(self):
        result = await input_processor({"user_input": "hello   world"})
        assert result["user_input"] == "hello world"

    async def test_handles_tabs(self):
        result = await input_processor({"user_input": "hello\tworld"})
        assert result["user_input"] == "hello world"

    async def test_handles_newlines(self):
        result = await input_processor({"user_input": "hello\nworld"})
        assert result["user_input"] == "hello world"

    async def test_handles_mixed_whitespace(self):
        result = await input_processor({"user_input": " hello \t world \n end "})
        assert result["user_input"] == "hello world end"

    async def test_empty_string_stays_empty(self):
        result = await input_processor({"user_input": ""})
        assert result["user_input"] == ""

    async def test_already_clean_input_unchanged(self):
        result = await input_processor({"user_input": "clean input text"})
        assert result["user_input"] == "clean input text"

    async def test_only_other_state_keys_untouched(self):
        result = await input_processor({"user_input": "  hi  ", "intent": "estimate"})
        assert "intent" not in result  # node only returns what it changes
