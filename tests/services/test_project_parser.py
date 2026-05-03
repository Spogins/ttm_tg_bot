# -*- coding: utf-8 -*-
import json

import pytest

from services.project_parser import (
    ParsedProject,
    _looks_like_tech_list,
    parse,
    parse_json,
    parse_text_description,
    parse_txt,
)


class TestLooksLikeTechList:
    def test_comma_separated_short_items(self):
        assert _looks_like_tech_list("Django, PostgreSQL, Redis, Docker") is True

    def test_single_item_returns_false(self):
        assert _looks_like_tech_list("Django") is False

    def test_long_item_returns_false(self):
        # items with >4 words are treated as a description, not a list
        assert _looks_like_tech_list("Some really long description text, another long phrase here") is False

    def test_newline_separated(self):
        assert _looks_like_tech_list("Django\nPostgreSQL\nRedis") is True

    def test_empty_string_returns_false(self):
        assert _looks_like_tech_list("") is False

    def test_single_word_returns_false(self):
        assert _looks_like_tech_list("Django") is False


class TestParseJson:
    def test_structured_format_with_tech_stack(self):
        data = {"files": ["main.py", "models.py"], "tech_stack": ["Django", "PostgreSQL"]}
        result = parse_json(data)
        assert result.tech_stack == ["Django", "PostgreSQL"]
        assert "main.py" in result.files

    def test_structured_format_detects_tech_from_files(self):
        data = {"files": ["requirements.txt", "manage.py"]}
        result = parse_json(data)
        assert "Python" in result.tech_stack
        assert "Django" in result.tech_stack

    def test_legacy_nested_dict(self):
        data = {"src": {"main.py": None, "models.py": None}}
        result = parse_json(data)
        assert isinstance(result.files, list)
        assert len(result.files) > 0

    def test_flat_list_format(self):
        data = ["main.py", "requirements.txt", "docker-compose.yml"]
        result = parse_json(data)
        assert "Python" in result.tech_stack
        assert "Docker" in result.tech_stack

    def test_empty_files_returns_empty(self):
        result = parse_json({"files": []})
        assert result.files == []
        assert result.tech_stack == []

    def test_raw_is_always_dict(self):
        result = parse_json(["file.py"])
        assert isinstance(result.raw, dict)

    def test_detects_django_apps(self):
        data = {"files": ["users/apps.py", "orders/apps.py"]}
        result = parse_json(data)
        assert "users" in result.modules or "orders" in result.modules


class TestParseTxt:
    def test_plain_paths(self):
        text = "src/main.py\nsrc/models.py\nrequirements.txt"
        result = parse_txt(text)
        assert any("requirements.txt" in f for f in result.files)

    def test_ascii_tree_characters_stripped(self):
        text = "├── requirements.txt\n└── manage.py"
        result = parse_txt(text)
        # tree chars should not appear in parsed file names
        assert all("├" not in f and "└" not in f and "─" not in f for f in result.files)

    def test_tech_detection_from_files(self):
        text = "requirements.txt\ndocker-compose.yml"
        result = parse_txt(text)
        assert "Python" in result.tech_stack
        assert "Docker" in result.tech_stack

    def test_comments_skipped(self):
        text = "# this is a comment\nrequirements.txt"
        result = parse_txt(text)
        assert not any("#" in f for f in result.files)

    def test_returns_parsed_project(self):
        assert isinstance(parse_txt("requirements.txt"), ParsedProject)


class TestParseTextDescription:
    def test_comma_list_taken_as_is(self):
        result = parse_text_description("Django, PostgreSQL, Redis, Docker")
        assert "Django" in result.tech_stack
        assert "PostgreSQL" in result.tech_stack
        assert "Redis" in result.tech_stack

    def test_known_tech_extracted_from_prose(self):
        text = "We use Django for the backend and PostgreSQL as the database."
        result = parse_text_description(text)
        assert "Django" in result.tech_stack
        assert "PostgreSQL" in result.tech_stack

    def test_unknown_tech_not_in_result_for_prose(self):
        text = "We use some custom framework nobody knows about."
        result = parse_text_description(text)
        assert result.tech_stack == []

    def test_files_always_empty(self):
        result = parse_text_description("Django, Redis")
        assert result.files == []

    def test_modules_always_empty(self):
        result = parse_text_description("Django, Redis")
        assert result.modules == []

    def test_dedup_tech_stack(self):
        result = parse_text_description("Django, django, DJANGO")
        # comma list path — items taken as-is; sorted set removes duplicates
        unique = sorted(set(result.tech_stack))
        assert len(result.tech_stack) == len(unique)


class TestParse:
    def test_json_bytes_parsed(self):
        data = json.dumps({"files": ["requirements.txt"]}).encode()
        result = parse(data)
        assert "Python" in result.tech_stack

    def test_json_string_parsed(self):
        data = json.dumps({"files": ["manage.py"]})
        result = parse(data)
        assert "Django" in result.tech_stack

    def test_ascii_tree_detected(self):
        text = "├── requirements.txt\n└── manage.py"
        result = parse(text)
        assert isinstance(result, ParsedProject)
        assert result.tech_stack  # tech detected from tree

    def test_slash_heavy_text_parsed_as_tree(self):
        text = "src/main.py\nsrc/models.py\nsrc/views.py\nsrc/urls.py"
        result = parse(text)
        assert isinstance(result, ParsedProject)

    def test_free_text_description_fallback(self):
        result = parse("We use Django and PostgreSQL")
        assert "Django" in result.tech_stack

    def test_too_deep_json_raises_valueerror_and_falls_back(self):
        # deeply nested JSON should not raise — parse falls back to text
        deep: dict = {}
        node = deep
        for _ in range(60):
            node["child"] = {}
            node = node["child"]
        data = json.dumps(deep)
        result = parse(data)
        assert isinstance(result, ParsedProject)
