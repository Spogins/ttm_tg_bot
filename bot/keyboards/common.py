# -*- coding: utf-8 -*-
"""
Inline keyboard builders for common bot interactions.
"""
from aiogram.types import ReplyKeyboardRemove  # noqa: E402
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MAIN_KB_BUTTONS = {
    "📋 Естимейт",
    "📅 Спринт",
    "📁 Проекты",
    "📊 История",
}

_MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Естимейт"), KeyboardButton(text="📅 Спринт")],
        [KeyboardButton(text="📁 Проекты"), KeyboardButton(text="📊 История")],
    ],
    resize_keyboard=True,
    persistent=True,
)


def main_keyboard(user=None) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    """Return the persistent reply keyboard, or ReplyKeyboardRemove when the user has no active project."""
    if user and getattr(user, "active_project_id", None):
        return _MAIN_KB
    return ReplyKeyboardRemove()


def start_keyboard() -> InlineKeyboardMarkup:
    """
    Return a keyboard with 'Add project' and 'Instructions' buttons.

    :return: InlineKeyboardMarkup with the add-project and instructions buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")],
            [InlineKeyboardButton(text="📖 Инструкция", callback_data="show_instructions")],
        ]
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
        # active project uses a noop callback so tapping the checkmark has no effect
        select_cb = "project:noop" if is_active else f"select_project:{p['project_id']}"  # noqa: E231
        buttons.append(
            [
                InlineKeyboardButton(text=label, callback_data=select_cb),
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


def voice_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Return a confirm/cancel keyboard shown after voice transcription.

    :return: InlineKeyboardMarkup with confirm and cancel buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="voice:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="voice:cancel"),
            ]
        ]
    )


def history_keyboard(estimations: list) -> InlineKeyboardMarkup:
    """
    Build a keyboard with one button per estimation for viewing its full details.

    :param estimations: List of Estimation instances, newest first.
    :return: InlineKeyboardMarkup with one button per estimation.
    """
    buttons = []
    for i, e in enumerate(estimations, 1):
        raw = e.task_name if getattr(e, "task_name", "") else e.task
        label = (raw[:30] + "…") if len(raw) > 30 else raw
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{i}. {label}", callback_data=f"estimation_detail:{e.estimation_id}"  # noqa: E231
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


_STATUS_LABELS = {
    "in_progress": "🔄 В процессе",
    "done": "✅ Выполнено",
    "cancelled": "❌ Не выполнено",
}


def status_keyboard(estimation_id: str, current_status: str) -> InlineKeyboardMarkup:
    """
    Build a single-row status selector for an estimation detail card.

    The current status is prefixed with '→ ' to indicate the active state.

    :param estimation_id: UUID of the estimation.
    :param current_status: The estimation's current status key.
    :return: InlineKeyboardMarkup with one button per status.
    """
    buttons = [
        InlineKeyboardButton(
            text=f"{'→ ' if s == current_status else ''}{label}",
            callback_data=f"set_status:{estimation_id}:{s}",  # noqa: E231
        )
        for s, label in _STATUS_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


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
