# -*- coding: utf-8 -*-
"""
Inline keyboard builders for common bot interactions.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_keyboard() -> InlineKeyboardMarkup:
    """
    Return a keyboard with a single 'Add project' button.

    :return: InlineKeyboardMarkup with the add-project button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")]]
    )


def projects_keyboard(projects: list[dict], active_project_id: str | None = None) -> InlineKeyboardMarkup:
    """
    Build a per-project row keyboard with select, update, and delete buttons.

    :param projects: List of project dicts with at least 'project_id' and 'name' keys.
    :param active_project_id: ID of the currently active project to mark with a checkmark.
    :return: InlineKeyboardMarkup with one row per project plus an add-project button.
    """
    buttons = []
    for p in projects:
        is_active = p["project_id"] == active_project_id
        label = f"{'✅' if is_active else '●'} {p['name']}"
        buttons.append(
            [
                InlineKeyboardButton(text=label, callback_data=f"select_project:{p['project_id']}"),
                InlineKeyboardButton(text="🔄", callback_data=f"update_project:{p['project_id']}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_project:{p['project_id']}"),
            ]
        )
    buttons.append([InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(project_id: str) -> InlineKeyboardMarkup:
    """
    Return a yes/cancel keyboard for the delete-confirmation prompt.

    :param project_id: UUID of the project to be deleted.
    :return: InlineKeyboardMarkup with confirm and cancel buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{project_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"),
            ]
        ]
    )


def estimation_keyboard() -> InlineKeyboardMarkup:
    """
    Return a keyboard with save, adjust, and details actions for an estimation result.

    :return: InlineKeyboardMarkup with save, adjust, and details buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="estimation:save"),
                InlineKeyboardButton(text="✏️ Скорректировать", callback_data="estimation:adjust"),
                InlineKeyboardButton(text="🔍 Подробнее", callback_data="estimation:details"),
            ]
        ]
    )


def sprint_result_keyboard() -> InlineKeyboardMarkup:
    """
    Return a keyboard shown after a sprint plan with an export-to-Markdown button.

    :return: InlineKeyboardMarkup with the export button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Экспорт в Markdown", callback_data="sprint:export"),
            ]
        ]
    )


def actual_hours_keyboard(estimation_id: str) -> InlineKeyboardMarkup:
    """
    Return a keyboard with a single button to enter actual hours for a task.

    :param estimation_id: UUID of the estimation to record actual hours for.
    :return: InlineKeyboardMarkup with the actual-hours button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Ввести реальное время",
                    callback_data=f"actual:{estimation_id}",
                )
            ]
        ]
    )
