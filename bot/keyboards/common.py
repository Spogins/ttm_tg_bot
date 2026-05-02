from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")]
    ])


def projects_keyboard(projects: list[dict], active_project_id: str | None = None) -> InlineKeyboardMarkup:
    buttons = []
    for p in projects:
        is_active = p["project_id"] == active_project_id
        label = f"{'✅' if is_active else '●'} {p['name']}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"select_project:{p['project_id']}"),
            InlineKeyboardButton(text="🔄", callback_data=f"update_project:{p['project_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_project:{p['project_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(project_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{project_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"),
        ]
    ])


def estimation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="estimation:save"),
            InlineKeyboardButton(text="✏️ Скорректировать", callback_data="estimation:adjust"),
            InlineKeyboardButton(text="🔍 Подробнее", callback_data="estimation:details"),
        ]
    ])
