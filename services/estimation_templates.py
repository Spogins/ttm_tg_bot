# -*- coding: utf-8 -*-
"""
Static task template definitions for quick estimation bootstrapping.
"""

TEMPLATES: list[dict] = [
    {
        "id": "rest_endpoint",
        "name": "REST эндпоинт",
        "text": (
            "Создать REST API эндпоинт с CRUD операциями (list, create, retrieve, update, delete), "
            "сериализатором с валидацией, фильтрацией, пагинацией и разграничением прав доступа."
        ),
    },
    {
        "id": "crud_ui",
        "name": "CRUD-интерфейс",
        "text": (
            "Разработать UI-страницу для управления записями: таблица со списком и сортировкой, "
            "форма создания и редактирования с валидацией, подтверждение удаления."
        ),
    },
    {
        "id": "auth",
        "name": "Аутентификация",
        "text": (
            "Реализовать систему аутентификации: регистрация, логин, выход, "
            "восстановление пароля, JWT-токены (access + refresh), защита роутов."
        ),
    },
    {
        "id": "external_api",
        "name": "Интеграция с API",
        "text": (
            "Интегрировать внешний сервис через API: авторизация (ключ/OAuth), "
            "отправка запросов, обработка ответов и ошибок, retry-логика, логирование."
        ),
    },
    {
        "id": "db_migration",
        "name": "Миграция БД",
        "text": (
            "Создать миграцию базы данных: новая таблица или изменение существующей схемы, "
            "добавление индексов, учёт обратной совместимости и возможности отката."
        ),
    },
    {
        "id": "notifications",
        "name": "Уведомления",
        "text": (
            "Реализовать систему уведомлений: email или push, шаблоны сообщений, "
            "очередь отправки (Celery / аналог), логирование доставки."
        ),
    },
]


def get_template(template_id: str) -> dict | None:
    """
    Return the template dict for the given id, or None if not found.

    :param template_id: Template identifier string.
    :return: Template dict or None.
    """
    return next((t for t in TEMPLATES if t["id"] == template_id), None)
