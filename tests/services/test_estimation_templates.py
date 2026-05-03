# -*- coding: utf-8 -*-
from services.estimation_templates import TEMPLATES, get_template


def test_templates_list_structure():
    assert isinstance(TEMPLATES, list) and len(TEMPLATES) > 0
    for t in TEMPLATES:
        assert {"id", "name", "text"} <= t.keys()
        assert all(isinstance(t[k], str) for k in ("id", "name", "text"))


def test_get_template_returns_correct():
    first = TEMPLATES[0]
    assert get_template(first["id"]) == first


def test_get_template_missing_returns_none():
    assert get_template("__nonexistent__") is None
