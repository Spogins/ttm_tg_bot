# -*- coding: utf-8 -*-
"""
Handlers for /start, /help, /instructions, /cancel, /stats, and /history commands.
"""
import uuid
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from bot.keyboards.common import (
    MAIN_KB_BUTTONS,
    actual_hours_keyboard,
    history_keyboard,
    main_keyboard,
    start_keyboard,
    status_keyboard,
)
from bot.states.states import ProjectStates
from config.settings import settings
from db.mongodb import estimations as estimations_db
from db.mongodb import projects as projects_db
from db.mongodb.models import ProjectTemplate
from services.estimation_breakdown import CATEGORY_NAMES

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
        icon, actual = _status_display(e)
        lines.append(f"{icon} {i}. {task} — <b>{e.total_hours} ч</b> → {actual}")

    return "\n".join(lines)


_STATUS_ICONS = {"done": "✅", "cancelled": "❌", "in_progress": "🔄"}
_STATUS_TEXT = {"done": "выполнено", "cancelled": "не выполнено", "in_progress": "в процессе"}


def _status_display(e) -> tuple[str, str]:
    status = getattr(e, "status", "in_progress")
    # backward compat: old records without explicit status but with actual_hours are "done"
    if status == "in_progress" and e.actual_hours is not None:
        status = "done"
    icon = _STATUS_ICONS.get(status, "🔄")
    if status == "done" and e.actual_hours is not None:
        text = f"{e.actual_hours} ч реально"
    else:
        text = _STATUS_TEXT.get(status, "в процессе")
    return icon, text


_COMPLEXITY_LABEL = {1: "Trivial", 2: "Simple", 3: "Medium", 4: "Hard", 5: "Very hard"}


def _format_estimation_detail(e) -> str:
    """
    Render a full estimation card as HTML for Telegram.

    :param e: Estimation instance.
    :return: HTML-formatted detail string.
    """
    complexity_label = _COMPLEXITY_LABEL.get(e.complexity, str(e.complexity))
    lines = [
        f"<b>📋 {e.task}</b>",
        "",
    ]
    if e.project_name:
        lines.append(f"<i>Проект: {e.project_name}</i>")
        lines.append("")
    if e.breakdown:
        lines.append("<b>Подзадачи:</b>")
        for key, hours in e.breakdown.items():
            name = CATEGORY_NAMES.get(key, key)
            lines.append(f"  • {name} — <b>{hours}h</b>")
        lines.append("")
    lines.append(f"⏱ <b>Итого:</b> {e.total_hours}h")  # noqa: E231
    lines.append(f"📊 <b>Сложность:</b> {complexity_label} ({e.complexity}/5)")  # noqa: E231
    if e.tech_stack:
        lines.append(f"🛠 <b>Стек:</b> {', '.join(e.tech_stack)}")  # noqa: E231
    if e.actual_hours is not None:
        diff = round(e.actual_hours - e.total_hours, 1)
        sign = "+" if diff > 0 else ""
        lines.append(f"✅ <b>Реально:</b> {e.actual_hours}h ({sign}{diff}h)")  # noqa: E231
    icon, status_text = _status_display(e)
    lines.append(f"\n{icon} <b>Статус:</b> {status_text}")  # noqa: E231
    return "\n".join(lines)


_INSTRUCTIONS = (
    "<b>📋 /estimate — оценка задачи</b>\n"
    "Опиши задачу текстом или голосовым — бот разобьёт её на подзадачи, посчитает часы, "
    "определит сложность и риски, покажет похожие задачи из истории.\n"
    "После выполнения укажи реальное время: бот напомнит через 36 ч.\n"
    "\n"
    "<i>Примеры:</i>\n"
    "<code>Фильтрация заказов по статусу и дате с сохранением в URL</code>\n"
    "<code>JWT авторизация: регистрация, логин, refresh token</code>\n"
    "<code>Интеграция с Nova Poshta: расчёт стоимости и создание ТТН</code>\n"
    "\n"
    "<b>📅 /sprint — планирование спринта</b>\n"
    "Укажи дневной capacity (часов/день), затем список задач — каждую с новой строки (макс. 10). "
    "Бот оценит каждую задачу, распределит по дням по принципу First-Fit и добавит +20% буфер "
    "для задач с внешними API. Готовый план можно скачать в Markdown.\n"
    "\n"
    "<b>📁 /projects — управление проектами</b>\n"
    "Добавь проект: название, краткое описание и стек технологий — бот учтёт контекст при каждой оценке.\n"
    "\n"
    "<i>Пример описания стека:</i>\n"
    "<code>Django + DRF, PostgreSQL, Celery + Redis, React.\n"
    "Деплой через Docker Compose. Интеграции: Nova Poshta, Monobank.</code>\n"
    "\n"
    "<i>Пример описания проекта:</i>\n"
    "<code>CRM для Instagram-магазина. Менеджеры принимают заказы\n"
    "в директе и вручную вносят в систему.\n"
    "Внешние API нестабильны — нужны retry и fallback.\n"
    "Celery-задачи для уведомлений тестировать отдельно.</code>\n"
    "\n"
    "<b>📊 /history — история оценок</b>\n"
    "Последние 10 оценок с плановым и реальным временем по каждой задаче.\n"
    "\n"
    "<b>📈 /stats — статистика точности</b>\n"
    "Среднее отклонение оценок, лучший и слабый тип задач, топ-3 недооценённых. "
    "Также показывает использование токенов за день и месяц.\n"
    "\n"
    "<b>🚫 /cancel — отменить действие</b>\n"
    "Выходит из любого активного диалога (оценка, спринт, добавление проекта)."
)

router = Router()


@router.message(F.text.in_(MAIN_KB_BUTTONS))
async def handle_main_keyboard(message: Message, state: FSMContext, user=None):
    """
    Dispatch bottom-keyboard button presses to the appropriate handler.

    Clears any active FSM state first so stale data does not bleed into the new flow.

    :param message: The incoming message matching one of the MAIN_KB_BUTTONS labels.
    :param state: The current FSM context.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    await state.clear()
    if message.text == "📋 Естимейт":
        from bot.handlers.estimation import cmd_estimate  # circular import — deferred intentionally

        await cmd_estimate(message, state, user=user)
    elif message.text == "📅 Спринт":
        from bot.handlers.estimation import cmd_sprint  # circular import — deferred intentionally

        await cmd_sprint(message, state, user=user)
    elif message.text == "📊 История":
        await cmd_history(message, user=user)
    elif message.text == "📁 Проекты":
        from bot.handlers.projects import cmd_projects  # circular import — deferred intentionally

        await cmd_projects(message, user=user)


@router.message(Command("start"))
async def cmd_start(message: Message, user=None):
    """
    Greet the user. Show full instructions on first visit, short greeting on repeat.

    :param message: The incoming message object.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    now = datetime.now(timezone.utc)
    is_new = user is not None and (now - user.created_at).total_seconds() < 30

    if is_new:
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n\n"
            "Я помогаю оценивать задачи и планировать спринты с помощью AI.\n\n" + _INSTRUCTIONS,
            parse_mode="HTML",
            reply_markup=main_keyboard(user),
        )
        await message.answer("Выбери действие:", reply_markup=start_keyboard())
    else:
        await message.answer(
            f"Привет, {message.from_user.first_name}!",
            reply_markup=main_keyboard(user),
        )


@router.message(Command("instructions"))
async def cmd_instructions(message: Message):
    """
    Send the full bot instructions. Duplicates the first-visit /start message.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer(_INSTRUCTIONS, parse_mode="HTML")


@router.callback_query(F.data == "show_instructions")
async def cb_show_instructions(callback: CallbackQuery):
    """
    Answer the 'Instructions' inline button with the full instructions text.

    :param callback: The callback query from the instructions button.
    :return: None
    """
    await callback.message.answer(_INSTRUCTIONS, parse_mode="HTML")
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Send a short list of available bot commands.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer(
        "<b>Команды:</b>\n\n"
        "/estimate — оценить задачу\n"
        "/sprint — спланировать спринт\n"
        "/projects — проекты\n"
        "/history — история оценок\n"
        "/stats — статистика\n"
        "/instructions — подробная справка\n"
        "/cancel — отменить действие",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user=None):
    """
    Clear the active FSM state and return to the main keyboard.

    :param message: The incoming message object.
    :param state: The current FSM context.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    current = await state.get_state()
    await state.clear()
    if current is None:
        await message.answer("Нет активного действия.", reply_markup=main_keyboard(user))
    else:
        await message.answer("Действие отменено.", reply_markup=main_keyboard(user))


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

    keyboard = history_keyboard(estimations) if estimations else None
    await message.answer(_format_history(estimations, project_name), parse_mode="HTML", reply_markup=keyboard)


def _estimation_detail_keyboard(estimation_id: str, estimation) -> InlineKeyboardMarkup:
    """
    Build the action keyboard for an estimation detail card.

    Includes status toggle row, actual-hours entry (when missing),
    and save-as-template button (only when actual_hours is already recorded).

    :param estimation_id: UUID of the estimation.
    :param estimation: Estimation instance.
    :return: Assembled InlineKeyboardMarkup.
    """
    rows = [status_keyboard(estimation_id, estimation.status).inline_keyboard[0]]
    if estimation.actual_hours is None:
        rows.append(actual_hours_keyboard(estimation_id).inline_keyboard[0])
    else:
        rows.append(
            [InlineKeyboardButton(text="📌 Сохранить как шаблон", callback_data=f"save_template:{estimation_id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("estimation_detail:"))
async def cb_estimation_detail(callback: CallbackQuery):
    """
    Show the full card for a saved estimation when the user taps it in the history list.

    :param callback: Callback query carrying the estimation_id.
    :return: None
    """
    estimation_id = callback.data.split(":", 1)[1]
    estimation = await estimations_db.get_estimation(estimation_id)

    if not estimation:
        await callback.answer("Оценка не найдена.", show_alert=True)
        return
    if estimation.user_id != callback.from_user.id:
        await callback.answer("Это не ваша оценка.", show_alert=True)
        return

    reply_markup = _estimation_detail_keyboard(estimation_id, estimation)
    await callback.message.answer(_format_estimation_detail(estimation), parse_mode="HTML", reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data.startswith("set_status:"))
async def cb_set_status(callback: CallbackQuery):
    """
    Toggle an estimation's status to the requested value and refresh the card in-place.

    No-ops silently if the status is already the requested value.

    :param callback: Callback query carrying 'set_status:<estimation_id>:<new_status>'.
    :return: None
    """
    parts = callback.data.split(":", 2)
    estimation_id, new_status = parts[1], parts[2]

    estimation = await estimations_db.get_estimation(estimation_id)
    if not estimation or estimation.user_id != callback.from_user.id:
        await callback.answer("Оценка не найдена.", show_alert=True)
        return

    if estimation.status == new_status:
        await callback.answer()
        return

    await estimations_db.set_status(estimation_id, new_status)
    estimation.status = new_status

    reply_markup = _estimation_detail_keyboard(estimation_id, estimation)
    await callback.message.edit_text(
        _format_estimation_detail(estimation), parse_mode="HTML", reply_markup=reply_markup
    )
    await callback.answer()


@router.callback_query(F.data.startswith("save_template:"))
async def cb_save_template_prompt(callback: CallbackQuery, state: FSMContext):
    """
    Start the save-as-template flow: validate ownership, store estimation_id, ask for a name.

    Only reachable from the detail card when actual_hours is already recorded.

    :param callback: Callback query carrying 'save_template:<estimation_id>'.
    :param state: The current FSM context.
    :return: None
    """
    estimation_id = callback.data.split(":", 1)[1]
    estimation = await estimations_db.get_estimation(estimation_id)
    if not estimation or estimation.user_id != callback.from_user.id:
        await callback.answer("Оценка не найдена.", show_alert=True)
        return
    if estimation.actual_hours is None:
        await callback.answer("Сначала введите реальное время.", show_alert=True)
        return

    await state.set_state(ProjectStates.awaiting_template_name)
    await state.update_data(template_estimation_id=estimation_id)
    suggested = estimation.task[:60]
    await callback.message.answer(
        f"Введите короткое название шаблона\n"
        f"(или отправьте /skip, чтобы использовать: <code>{suggested}</code>):",  # noqa: E231
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_template_name)
async def handle_template_name(message: Message, state: FSMContext, user=None):
    """
    Receive the template name, build a ProjectTemplate, persist it to MongoDB and Qdrant.

    :param message: Message containing a custom name or /skip.
    :param state: FSM context holding template_estimation_id.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    data = await state.get_data()
    estimation_id = data.get("template_estimation_id", "")
    await state.clear()

    estimation = await estimations_db.get_estimation(estimation_id)
    if not estimation or estimation.actual_hours is None:
        await message.answer("Ошибка: оценка не найдена. Начните заново.")
        return

    text = (message.text or "").strip()
    name = estimation.task[:60] if text == "/skip" or not text else text[:60]

    if estimation.total_hours > 0:
        deviation_pct = round((estimation.actual_hours - estimation.total_hours) / estimation.total_hours * 100, 1)
    else:
        deviation_pct = 0.0
    template = ProjectTemplate(
        template_id=str(uuid.uuid4()),
        estimation_id=estimation_id,
        name=name,
        task=estimation.task,
        total_hours=estimation.total_hours,
        actual_hours=estimation.actual_hours,
        deviation_pct=deviation_pct,
        scope=estimation.scope,
        tech_stack=estimation.tech_stack,
    )

    project_id = estimation.project_id or (user.active_project_id if user else None)
    if not project_id:
        await message.answer("⚠️ Нет активного проекта. Шаблон не сохранён.")
        return

    await projects_db.add_template(project_id, template)

    try:
        from services.indexer import index_template  # deferred to avoid circular import at module level

        await index_template(project_id, template)
    except Exception as e:
        logger.warning(f"Template Qdrant indexing failed for {template.template_id}: {e}")

    sign = "+" if deviation_pct >= 0 else ""
    await message.answer(
        f"📌 Шаблон <b>{name}</b> сохранён.\n"
        f"Оценка: {estimation.total_hours}h → Реально: {estimation.actual_hours}h "
        f"({sign}{deviation_pct}%)",
        parse_mode="HTML",
    )
