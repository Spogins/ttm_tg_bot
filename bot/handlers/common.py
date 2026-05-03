# -*- coding: utf-8 -*-
"""
Handlers for /start, /help, /cancel, /stats, and /history commands.
"""
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.common import start_keyboard
from config.settings import settings
from db.mongodb import estimations as estimations_db
from db.mongodb import projects as projects_db

_MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def _fmt_date(dt: datetime) -> str:
    return f"{dt.day} {_MONTHS_RU[dt.month - 1]}"


def _format_history(estimations: list, project_name: str = "") -> str:
    """
    Render a numbered history list as an HTML string for Telegram.

    :param estimations: List of Estimation instances, newest first.
    :param project_name: Active project name for the header; empty string omits it.
    :return: HTML-formatted string.
    """
    header = "<b>📋 История оценок"
    if project_name:
        header += f" — {project_name}"
    header += "</b>"

    if not estimations:
        return header + "\n\n<i>Нет сохранённых оценок.</i>"

    lines = [header, ""]
    for i, e in enumerate(estimations, 1):
        task = (e.task[:42] + "…") if len(e.task) > 42 else e.task
        actual = f"{e.actual_hours} ч реально" if e.actual_hours is not None else "—"
        lines.append(f"{i}. {task} — <b>{e.total_hours} ч</b> → {actual} ({_fmt_date(e.created_at)})")

    return "\n".join(lines)


router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Greet the user and show the main keyboard.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Я помогу оценивать задачи и планировать спринты.\n"
        "Для начала добавь проект.",
        reply_markup=start_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Send the full list of available bot commands.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer(
        "<b>Команды бота:</b>\n\n"
        "/projects — список проектов\n"
        "/estimate — оценить задачу\n"
        "/sprint — планировщик спринта\n"
        "/stats — статистика оценок и токенов\n"
        "/history — последние 10 оценок\n"
        "/cancel — выйти из текущего действия",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """
    Clear the active FSM state and inform the user.

    :param message: The incoming message object.
    :param state: The current FSM context.
    :return: None
    """
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия.")
        return
    await state.clear()
    await message.answer("Действие отменено.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, user=None):
    """
    Show estimation accuracy stats and token usage for the current user.

    :param message: The incoming message object.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    stats = await estimations_db.get_velocity_stats(message.from_user.id)

    lines = [
        "<b>📊 Статистика оценок (последние 30 дней)</b>",
        "─────────────────────────────────────",
        f"Всего оценок: {stats['total']}",
        f"С реальным временем: {stats['with_actual']}",
        "",
    ]

    if stats["with_actual"] > 0:
        dev = stats["avg_deviation"]
        sign = "+" if dev > 0 else ""
        label = "недооцениваешь" if dev > 0 else ("переоцениваешь" if dev < 0 else "точно")
        lines += [
            "<b>Точность:</b>",
            f"• Среднее отклонение: {sign}{dev}% ({label})",
        ]
        if stats["best_type"]:
            name, val = stats["best_type"]
            s = "+" if val >= 0 else ""
            lines.append(f"• Лучший тип задач: {name} ({s}{val}%)")
        if stats["worst_type"]:
            name, val = stats["worst_type"]
            s = "+" if val >= 0 else ""
            lines.append(f"• Слабый тип задач: {name} ({s}{val}%)")
        lines.append("")

        if stats["top_underestimated"]:
            lines.append("<b>Топ-3 недооцениваемых:</b>")
            for i, (task, d) in enumerate(stats["top_underestimated"], 1):
                lines.append(f"{i}. {task}: +{d}%")
            lines.append("")
    else:
        lines += [
            "<i>Нет оценок с реальным временем.</i>",
            "<i>После завершения задачи введи фактические часы — бот напомнит через 36 ч.</i>",
            "",
        ]

    daily = user.tokens.daily_used if user else 0
    monthly = user.tokens.monthly_used if user else 0
    lines += [
        "<b>Использование токенов:</b>",
        f"• Сегодня: {daily:,} / {settings.daily_token_limit:,}",  # noqa: E231
        f"• Месяц: {monthly:,} / {settings.monthly_token_limit:,}",  # noqa: E231
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message, user=None):
    """
    Show the last 10 estimations with estimated vs actual hours.

    :param message: The incoming message object.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    estimations = await estimations_db.get_user_estimations(message.from_user.id, limit=10)

    project_name = ""
    if user and user.active_project_id:
        project = await projects_db.get_project(user.active_project_id)
        project_name = project.name if project else ""

    await message.answer(_format_history(estimations, project_name), parse_mode="HTML")
