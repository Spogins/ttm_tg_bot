# -*- coding: utf-8 -*-
"""Inline keyboard builders for the estimation flow: scope selection, estimation mode, and breakdown confirmation."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.estimation_breakdown import CATEGORY_NAMES, calculate_total

_SCOPE_MAIN = [("Backend", "backend"), ("Frontend", "frontend"), ("Fullstack", "fullstack")]
_SCOPE_EXTRAS = [("+ QA", "qa"), ("+ DevOps", "devops")]

_MODE_LABELS = {
    "optimistic": "🟢 Оптимистично ×0.8",
    "realistic": "🟡 Реалистично ×1.0",
    "pessimistic": "🔴 Пессимистично ×1.3",
}


def scope_keyboard(selected_main: str | None, selected_extras: list[str]) -> InlineKeyboardMarkup:
    """
    Build the scope selection keyboard with a radio row (main) and checkbox row (extras).

    :param selected_main: Currently selected main scope id, or None if nothing selected yet.
    :param selected_extras: List of currently selected extra scope ids.
    :return: InlineKeyboardMarkup with scope toggles and a continue button.
    """
    main_row = [
        InlineKeyboardButton(
            text=f"{'✅' if nid == selected_main else '◻️'} {label}",
            callback_data=f"scope_main:{nid}",  # noqa: E231
        )
        for label, nid in _SCOPE_MAIN
    ]
    extras_row = [
        InlineKeyboardButton(
            text=f"{'✅' if nid in selected_extras else '◻️'} {label}",
            callback_data=f"scope_extra:{nid}",  # noqa: E231
        )
        for label, nid in _SCOPE_EXTRAS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            main_row,
            extras_row,
            [InlineKeyboardButton(text="Продолжить →", callback_data="scope:continue")],
        ]
    )


def mode_keyboard() -> InlineKeyboardMarkup:
    """
    Build the estimation mode selector keyboard (optimistic / realistic / pessimistic).

    :return: InlineKeyboardMarkup with one button per mode.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"mode:{mid}")] for mid, label in _MODE_LABELS.items()
        ]
    )


def breakdown_keyboard(breakdown: dict[str, float], toggles: dict[str, bool]) -> InlineKeyboardMarkup:
    """
    Build the interactive breakdown confirmation keyboard.

    Categories with zero hours are hidden. The 'implementation' category is locked (noop tap).
    A running total row and a confirm button are appended at the bottom.

    :param breakdown: Dict mapping category key to scaled hours.
    :param toggles: Dict mapping category key to its enabled state.
    :return: InlineKeyboardMarkup with toggle buttons, total row, and confirm button.
    """
    rows = []
    for cat, hours in breakdown.items():
        if hours <= 0:
            continue
        is_on = toggles.get(cat, True)
        is_core = cat == "implementation"
        label = f"{'✅' if is_on else '☐'} {CATEGORY_NAMES[cat]} — {hours}h"
        cb = "breakdown:noop" if is_core else f"breakdown:toggle:{cat}"  # noqa: E231
        rows.append([InlineKeyboardButton(text=label, callback_data=cb)])

    total = calculate_total(breakdown, toggles)
    rows.append([InlineKeyboardButton(text=f"─── Итого: {total}h ───", callback_data="breakdown:noop")])
    rows.append([InlineKeyboardButton(text="✅ Сохранить оценку", callback_data="breakdown:confirm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
