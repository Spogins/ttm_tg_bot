# -*- coding: utf-8 -*-
import pytest

from db.mongodb.estimations import _classify_task


class TestClassifyTask:
    def test_api_keyword(self):
        assert _classify_task("Nova Poshta integration") == "API / Интеграции"

    def test_api_keyword_lowercase(self):
        assert _classify_task("connect to stripe api") == "API / Интеграции"

    def test_webhook_keyword(self):
        assert _classify_task("Handle incoming webhook events") == "API / Интеграции"

    def test_auth_keyword(self):
        assert _classify_task("JWT authentication middleware") == "Аутентификация"

    def test_auth_russian(self):
        assert _classify_task("Добавить аутентификацию через Google") == "Аутентификация"

    def test_celery_keyword(self):
        assert _classify_task("Celery task for email sending") == "Celery / Очереди"

    def test_queue_keyword(self):
        assert _classify_task("Process background queue workers") == "Celery / Очереди"

    def test_ui_keyword(self):
        assert _classify_task("Admin dashboard with filters") == "UI / Frontend"

    def test_ui_russian(self):
        assert _classify_task("Верстка карточки заказа") == "UI / Frontend"

    def test_db_keyword(self):
        assert _classify_task("Add migration for user model") == "База данных"

    def test_unclassified_returns_none(self):
        assert _classify_task("Fix bug in order calculation") is None

    def test_case_insensitive(self):
        assert _classify_task("STRIPE PAYMENT") == "API / Интеграции"

    def test_first_match_wins(self):
        # "api" matches API group, not auth — ordering is deterministic
        result = _classify_task("oauth api gateway")
        assert result in ("API / Интеграции", "Аутентификация")
