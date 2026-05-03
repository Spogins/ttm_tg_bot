# -*- coding: utf-8 -*-
"""
Tests for services/project_claude.py.

The Anthropic client is mocked so no real API calls are made.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.project_claude import extract_tech_stack


def _mock_response(text: str):
    """Build a minimal fake Anthropic response with the given text."""
    content = MagicMock()
    content.text = text
    response = MagicMock()
    response.content = [content]
    return response


class TestExtractTechStack:
    @pytest.mark.asyncio
    async def test_returns_sorted_list(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_response('["Redis", "Django", "PostgreSQL"]'))
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("Django, Redis, PostgreSQL")
        assert result == sorted(result)

    @pytest.mark.asyncio
    async def test_deduplicates_entries(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_response('["Django", "Django", "Redis"]'))
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("Django, Django, Redis")
        assert result.count("Django") == 1

    @pytest.mark.asyncio
    async def test_extracts_json_from_wrapped_response(self):
        # Claude sometimes wraps JSON in extra prose
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_response('Sure! Here is the result: ["Django", "Redis"]')
        )
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("Django, Redis")
        assert "Django" in result
        assert "Redis" in result

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("Django, PostgreSQL, Redis")
        # fallback: comma-split of the raw input
        assert "Django" in result
        assert "PostgreSQL" in result
        assert "Redis" in result

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_response("not valid json at all"))
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("Django, Redis")
        # fallback: comma-split
        assert "Django" in result
        assert "Redis" in result

    @pytest.mark.asyncio
    async def test_description_included_in_prompt(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_mock_response('["Django"]'))
        with patch("services.project_claude.get_client", return_value=mock_client):
            await extract_tech_stack("Django", description="CRM project")
        call_kwargs = mock_client.messages.create.call_args
        prompt = call_kwargs.kwargs["messages"][0]["content"]
        assert "CRM project" in prompt

    @pytest.mark.asyncio
    async def test_empty_stack_text_fallback_returns_empty(self):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("err"))
        with patch("services.project_claude.get_client", return_value=mock_client):
            result = await extract_tech_stack("   ")
        # fallback splits by comma+newline; whitespace-only gives empty after strip
        assert result == []
