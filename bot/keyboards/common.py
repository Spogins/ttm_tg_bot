from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")]
    ])


def projects_keyboard(projects: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"select_project:{p['project_id']}")]
        for p in projects
    ]
    buttons.append([InlineKeyboardButton(text="➕ Добавить проект", callback_data="add_project")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def estimation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="estimation:save"),
            InlineKeyboardButton(text="✏️ Скорректировать", callback_data="estimation:adjust"),
            InlineKeyboardButton(text="🔍 Подробнее", callback_data="estimation:details"),
        ]
    ])
