# -*- coding: utf-8 -*-
"""
Claude-based project tech stack extraction and description normalization.
"""
import json
import re

from loguru import logger

from agent.llm import HAIKU_MODEL, get_client

_SYSTEM = (
    "You are a technical project analyzer. "
    "Given a tech stack and project description, return ONLY a valid JSON array "
    "of normalized technology names. Correct obvious typos (e.g. 'PostgresSQL' → 'PostgreSQL'). "
    "Capitalize properly (e.g. 'django' → 'Django', 'redis' → 'Redis'). "
    "Include every technology mentioned. No explanation, no markdown — just the JSON array."
)


async def extract_tech_stack(stack_text: str, description: str = "") -> list[str]:
    """
    Ask Claude Haiku to normalize and extract a tech stack list from user input.

    Falls back to splitting the raw stack_text by comma if the API call fails.

    :param stack_text: Raw tech stack text from the user.
    :param description: Optional project description for additional context.
    :return: Sorted list of normalized technology names.
    """
    prompt = f"Tech stack: {stack_text}"
    if description:
        prompt += f"\nProject description: {description}"

    try:
        client = get_client()
        response = await client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=200,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # extract JSON array even if Claude wraps it in extra text
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            return sorted(set(json.loads(match.group())))
    except Exception as e:
        logger.warning(f"project_claude extract_tech_stack error: {e}")

    # fallback: split by comma
    return sorted({t.strip() for t in re.split(r"[,\n]+", stack_text) if t.strip()})
