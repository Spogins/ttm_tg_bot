# -*- coding: utf-8 -*-
"""
Shared Anthropic async client singleton.
"""
import anthropic

from config.settings import settings

_client: anthropic.AsyncAnthropic | None = None

# cheap model used for classification, clarification and risk nodes
HAIKU_MODEL = "claude-haiku-4-5-20251001"


def get_client() -> anthropic.AsyncAnthropic:
    """
    Return the module-level Anthropic client, creating it on first call.

    :return: The initialized AsyncAnthropic instance.
    """
    global _client
    if _client is None:  # lazy init on first call
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client
