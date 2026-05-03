# -*- coding: utf-8 -*-
"""Handlers for task estimation: scope selection, graph invocation, mode selection, breakdown confirmation."""
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from loguru import logger

from agent.runner import run_agent, run_sprint_agent
from bot.handlers.common import _format_history
from bot.keyboards.common import history_keyboard, sprint_result_keyboard
from bot.keyboards.estimation_flow import breakdown_keyboard, mode_keyboard, scope_keyboard
from bot.states.states import EstimationStates, SprintStates
from db.mongodb import estimations as estimations_db
from db.mongodb import projects as projects_db
from services.estimation_breakdown import DEFAULT_TOGGLES, apply_mode, calculate_total, categorize_subtasks
from services.estimation_indexer import index_estimation, update_actual_hours
from services.sprint_exporter import generate_sprint_markdown

router = Router()


def _build_scope(fsm_data: dict) -> list[str]:
    """
    Assemble the ordered scope list from FSM data keys set during scope selection.

    :param fsm_data: Current FSM data dict with optional 'scope_main' and 'scope_extras' keys.
    :return: Ordered list like ['backend', 'qa'].
    """
    scope = []
    if fsm_data.get("scope_main"):
        scope.append(fsm_data["scope_main"])
    scope.extend(fsm_data.get("scope_extras", []))
    return scope


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext, user=None):
    """
    Start the estimation flow by showing the scope selector keyboard.

    Blocks the flow if the user has no active project and asks them to add one first.

    :param message: The incoming /estimate command message.
    :param state: The current FSM context.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    if not user or not user.active_project_id:
        from bot.keyboards.common import start_keyboard

        await message.answer(
            "Для оценки задач нужен проект.\nДобавьте хотя бы один проект.",
            reply_markup=start_keyboard(),
        )
        return

    # restore the last scope used for this project so the user doesn't reselect every time
    project = await projects_db.get_project(user.active_project_id)
    saved_scope: list[str] = project.default_scope if project else []
    # split saved scope back into main + extras
    _MAIN_OPTIONS = {"backend", "frontend", "fullstack"}
    saved_main = next((s for s in saved_scope if s in _MAIN_OPTIONS), None)
    saved_extras = [s for s in saved_scope if s not in _MAIN_OPTIONS]

    await state.set_state(EstimationStates.selecting_scope)
    await state.update_data(scope_main=saved_main, scope_extras=saved_extras)
    await message.answer(
        "Выберите тип задачи:",
        reply_markup=scope_keyboard(selected_main=saved_main, selected_extras=saved_extras),
    )


@router.callback_query(EstimationStates.selecting_scope, F.data.startswith("scope_main:"))
async def cb_scope_main(callback: CallbackQuery, state: FSMContext):
    """
    Toggle a main scope option (Backend / Frontend / Fullstack) and refresh the keyboard.

    Tapping the already-selected option deselects it (radio toggle).

    :param callback: Callback query carrying 'scope_main:<option_id>'.
    :param state: The current FSM context.
    :return: None
    """
    selected = callback.data.split(":", 1)[1]
    data = await state.get_data()
    scope_main = None if data.get("scope_main") == selected else selected
    await state.update_data(scope_main=scope_main)
    await callback.message.edit_reply_markup(
        reply_markup=scope_keyboard(selected_main=scope_main, selected_extras=data.get("scope_extras", []))
    )
    await callback.answer()


@router.callback_query(EstimationStates.selecting_scope, F.data.startswith("scope_extra:"))
async def cb_scope_extra(callback: CallbackQuery, state: FSMContext):
    """
    Toggle an extra scope checkbox (QA / DevOps) and refresh the keyboard.

    :param callback: Callback query carrying 'scope_extra:<option_id>'.
    :param state: The current FSM context.
    :return: None
    """
    extra = callback.data.split(":", 1)[1]
    data = await state.get_data()
    extras: list = list(data.get("scope_extras", []))
    if extra in extras:
        extras.remove(extra)
    else:
        extras.append(extra)
    await state.update_data(scope_extras=extras)
    await callback.message.edit_reply_markup(
        reply_markup=scope_keyboard(selected_main=data.get("scope_main"), selected_extras=extras)
    )
    await callback.answer()


@router.callback_query(EstimationStates.selecting_scope, F.data == "scope:continue")
async def cb_scope_continue(callback: CallbackQuery, state: FSMContext, user=None):
    """
    Validate scope selection and advance directly to task input.

    Shows an alert if no main scope (Backend / Frontend / Fullstack) was selected.

    :param callback: Callback query from the 'Продолжить →' button.
    :param state: The current FSM context.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    data = await state.get_data()
    if not data.get("scope_main"):
        await callback.answer("Выберите тип задачи (Backend / Frontend / Fullstack).", show_alert=True)
        return

    # persist the chosen scope on the project so it's pre-selected next time
    scope = _build_scope(data)
    if user and user.active_project_id:
        await projects_db.update_project(user.active_project_id, default_scope=scope)

    await state.set_state(EstimationStates.awaiting_task)
    await callback.message.edit_text("Опишите задачу, которую нужно оценить.\nМожно голосовым сообщением или текстом.")
    await callback.answer()


async def _run_task(
    send, state: FSMContext, user_id: int, text: str, project_id: str | None, *, scope: list[str] | None = None
) -> None:
    """
    Run the agent graph for a task text and update FSM state based on the result.

    :param send: Async callable matching message.answer signature (sends a message, returns Message).
    :param state: Current FSM context.
    :param user_id: Telegram user ID.
    :param text: Task description text to process.
    :param project_id: Active project UUID, or None.
    :return: None
    """
    if len(text) > 5000:
        await send("⚠️ Описание задачи слишком длинное (макс. 5000 символов).")
        return

    progress = await send("⏳ Анализирую задачу...")
    result = await run_agent(user_id, text, project_id=project_id, scope=scope or [])
    response_text = result.get("formatted_response", "")

    if result.get("clarification_needed"):
        await state.set_state(EstimationStates.clarifying)
        await progress.edit_text(response_text)

    elif result.get("estimation") is not None:
        subtasks = result["estimation"].get("subtasks", [])
        breakdown = categorize_subtasks(subtasks)
        await state.update_data(
            pending_estimation=result["estimation"],
            pending_task=text,
            pending_project_id=project_id,
            pending_breakdown=breakdown,
            pending_scope=scope or [],
        )
        await state.set_state(EstimationStates.selecting_mode)
        await progress.edit_text(response_text, reply_markup=mode_keyboard())

    else:
        await state.clear()
        await progress.edit_text(response_text)


@router.message(EstimationStates.awaiting_task)
@router.message(EstimationStates.clarifying)  # clarification answer re-enters the graph
async def handle_task_input(message: Message, state: FSMContext, user=None):
    """
    Run the agent graph and route to clarification, confirmation, or done based on the result.

    :param message: The incoming message with task description or clarification answer.
    :param state: The current FSM context.
    :param user: Injected User object from UserMiddleware.
    :return: None
    """
    project_id = user.active_project_id if user else None
    data = await state.get_data()
    scope = _build_scope(data)
    await _run_task(message.answer, state, message.from_user.id, message.text or "", project_id, scope=scope)


@router.callback_query(F.data == "voice:confirm")
async def cb_voice_confirm(callback: CallbackQuery, state: FSMContext, user=None):
    """
    Process the stored voice transcript through the agent after the user confirms it.

    Guards against stale confirm taps (e.g. from a previous session) by checking
    that the user is actually in an estimation-related state before proceeding.

    :param callback: Callback query from the confirm button.
    :param state: FSM context holding the pending transcript.
    :param user: User object injected by UserMiddleware.
    :return: None
    """
    current_state = await state.get_state()
    estimation_states = {
        EstimationStates.awaiting_task.state,
        EstimationStates.clarifying.state,
    }
    if current_state not in estimation_states:
        await callback.answer("Нет активной оценки. Начните заново.", show_alert=True)
        return

    data = await state.get_data()
    transcript = data.get("pending_voice_transcript", "")
    await state.update_data(pending_voice_transcript=None)
    if not transcript:
        await callback.answer("Текст не найден. Попробуйте ещё раз.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    project_id = user.active_project_id if user else None
    scope = _build_scope(data)
    await _run_task(callback.message.answer, state, callback.from_user.id, transcript, project_id, scope=scope)


@router.callback_query(F.data == "voice:cancel")
async def cb_voice_cancel(callback: CallbackQuery, state: FSMContext):
    """
    Discard the pending voice transcript and notify the user.

    :param callback: Callback query from the cancel button.
    :param state: FSM context to clean up.
    :return: None
    """
    await state.update_data(pending_voice_transcript=None)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено.")


@router.callback_query(EstimationStates.selecting_mode, F.data.startswith("mode:"))
async def cb_mode_select(callback: CallbackQuery, state: FSMContext):
    """
    Apply the selected estimation mode multiplier and show the breakdown toggle keyboard.

    :param callback: Callback query carrying 'mode:<pessimistic|realistic|optimistic>'.
    :param state: The current FSM context with pending_breakdown stored.
    :return: None
    """
    mode = callback.data.split(":", 1)[1]
    data = await state.get_data()
    breakdown = data.get("pending_breakdown", {})
    scaled = apply_mode(breakdown, mode)
    toggles = dict(DEFAULT_TOGGLES)
    await state.update_data(pending_mode=mode, pending_breakdown_scaled=scaled, pending_toggles=toggles)
    await state.set_state(EstimationStates.confirming_breakdown)
    await callback.message.edit_reply_markup(reply_markup=breakdown_keyboard(scaled, toggles))
    await callback.answer()


@router.callback_query(EstimationStates.confirming_breakdown, F.data.startswith("breakdown:toggle:"))
async def cb_breakdown_toggle(callback: CallbackQuery, state: FSMContext):
    """
    Flip the enabled/disabled toggle for a breakdown category and refresh the keyboard.

    :param callback: Callback query carrying 'breakdown:toggle:<category>'.
    :param state: The current FSM context with pending_toggles and pending_breakdown_scaled.
    :return: None
    """
    cat = callback.data.split(":", 2)[2]
    data = await state.get_data()
    toggles = dict(data.get("pending_toggles", DEFAULT_TOGGLES))
    toggles[cat] = not toggles.get(cat, True)
    await state.update_data(pending_toggles=toggles)
    breakdown = data.get("pending_breakdown_scaled", {})
    await callback.message.edit_reply_markup(reply_markup=breakdown_keyboard(breakdown, toggles))
    await callback.answer()


@router.callback_query(EstimationStates.confirming_breakdown, F.data == "breakdown:noop")
async def cb_breakdown_noop(callback: CallbackQuery):
    """
    Silently acknowledge taps on non-interactive breakdown items (total row, locked categories).

    :param callback: Callback query with 'breakdown:noop' data.
    :return: None
    """
    await callback.answer()


@router.callback_query(EstimationStates.confirming_breakdown, F.data == "breakdown:confirm")
async def cb_breakdown_confirm(callback: CallbackQuery, state: FSMContext):
    """
    Persist the finalized estimation to MongoDB, index in Qdrant, and show updated history.

    Only enabled breakdown categories are stored in the final breakdown dict.
    Qdrant indexing failure is non-fatal — the estimation is still saved to MongoDB.

    :param callback: Callback query from the 'Сохранить оценку' button.
    :param state: The current FSM context with pending estimation data.
    :return: None
    """
    user_id = callback.from_user.id
    logger.info(f"cb_breakdown_confirm: user={user_id}")

    data = await state.get_data()
    estimation = data.get("pending_estimation")
    if not estimation:
        await callback.answer("Нет данных для сохранения.", show_alert=True)
        return

    breakdown = data.get("pending_breakdown_scaled", {})
    toggles = data.get("pending_toggles", DEFAULT_TOGGLES)
    total_hours = calculate_total(breakdown, toggles)
    final_breakdown = {cat: hours for cat, hours in breakdown.items() if toggles.get(cat, True)}
    mode = data.get("pending_mode", "realistic")
    scope = data.get("pending_scope", [])
    task = data.get("pending_task", "")
    project_id = data.get("pending_project_id")

    project = await projects_db.get_project(project_id) if project_id else None
    saved = await estimations_db.save_estimation(
        user_id=user_id,
        task=task,
        total_hours=total_hours,
        complexity=estimation["complexity"],
        tech_stack=project.tech_stack if project else [],
        breakdown=final_breakdown,
        project_id=project_id,
        project_name=project.name if project else "",
        reminder_at=datetime.now(timezone.utc) + timedelta(hours=36),
        scope=scope,
        estimation_mode=mode,
    )
    logger.info(f"cb_breakdown_confirm: saved estimation_id={saved.estimation_id}")

    try:
        await index_estimation(saved)
    except Exception as e:
        logger.warning(f"Qdrant indexing failed for {saved.estimation_id}: {e}")

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Оценка сохранена!")

    estimations = await estimations_db.get_user_estimations(user_id, limit=10)
    project_name = project.name if project else ""
    await callback.message.answer(
        _format_history(estimations, project_name),
        parse_mode="HTML",
        reply_markup=history_keyboard(estimations) if estimations else None,
    )


@router.callback_query(F.data.startswith("actual:"))
async def cb_actual_hours_prompt(callback: CallbackQuery, state: FSMContext):
    """
    Verify estimation ownership, store the estimation_id, enter awaiting_actual_hours state.

    :param callback: The callback query from the actual-hours button.
    :param state: The current FSM context.
    :return: None
    """
    estimation_id = callback.data.split(":", 1)[1]
    estimation = await estimations_db.get_estimation(estimation_id)
    if not estimation or estimation.user_id != callback.from_user.id:
        await callback.answer("Оценка не найдена.", show_alert=True)
        return
    await state.update_data(estimation_id=estimation_id)
    await state.set_state(EstimationStates.awaiting_actual_hours)
    await callback.message.answer("Введи реальное время в часах (например: `4.5`):")
    await callback.answer()


@router.message(EstimationStates.awaiting_actual_hours)
async def handle_actual_hours(message: Message, state: FSMContext):
    """
    Validate the actual hours input, persist to MongoDB and Qdrant, then clear state.

    :param message: Message containing the actual hours as text.
    :param state: The current FSM context with estimation_id stored.
    :return: None
    """
    text = (message.text or "").strip().replace(",", ".")
    try:
        hours = float(text)
        if hours <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи положительное число, например `4.5`.")
        return

    data = await state.get_data()
    estimation_id = data.get("estimation_id")
    user_id = message.from_user.id

    await estimations_db.set_actual_hours(estimation_id, hours)

    try:
        estimation = await estimations_db.get_estimation(estimation_id)
        if estimation:
            await update_actual_hours(estimation_id, user_id, hours)
    except Exception as e:
        logger.warning(f"Qdrant actual_hours update failed for {estimation_id}: {e}")

    await state.clear()
    await message.answer(f"✅ Записано! *{hours} ч* реального времени.", parse_mode="Markdown")


@router.callback_query(F.data == "sprint:export")
async def cb_export_sprint(callback: CallbackQuery, state: FSMContext):
    """
    Generate a Markdown file from the last sprint plan and send it as a document.

    :param callback: The callback query from the export button.
    :param state: FSM context holding last_sprint_plan and last_sprint_hours.
    :return: None
    """
    data = await state.get_data()
    sprint_plan = data.get("last_sprint_plan")

    if not sprint_plan:
        await callback.answer("Нет данных для экспорта.", show_alert=True)
        return

    hours_per_day = data.get("last_sprint_hours", 8.0)
    content = generate_sprint_markdown(sprint_plan, hours_per_day)
    project_name = sprint_plan.get("project_name", "sprint")
    safe_name = project_name.replace(" ", "_") or "sprint"
    filename = f"{safe_name}_plan.md"

    await callback.message.answer_document(
        BufferedInputFile(content.encode("utf-8"), filename=filename),
        caption="📤 Sprint Plan в Markdown",
    )
    await state.clear()
    await callback.answer()


@router.message(Command("sprint"))
async def cmd_sprint(message: Message, state: FSMContext, user=None):
    """
    Enter sprint planning: ask for daily capacity in hours.

    Blocks the flow if the user has no active project and asks them to add one first.

    :param message: The incoming /sprint command message.
    :param state: The current FSM context.
    :param user: User instance injected by UserMiddleware.
    :return: None
    """
    if not user or not user.active_project_id:
        from bot.keyboards.common import start_keyboard

        await message.answer(
            "Для планирования спринта нужен проект.\nДобавьте хотя бы один проект.",
            reply_markup=start_keyboard(),
        )
        return
    await state.set_state(SprintStates.awaiting_hours)
    await message.answer(
        "📅 *Sprint Planner*\n\n"
        "Сколько рабочих часов в день у тебя в этом спринте?\n"
        "Введи число (например: `6` или `7.5`)"
    )


@router.message(SprintStates.awaiting_hours)
async def handle_sprint_hours(message: Message, state: FSMContext):
    """
    Validate and store daily hours, then ask for the task list.

    :param message: Message containing hours per day as text.
    :param state: The current FSM context.
    :return: None
    """
    text = (message.text or "").strip().replace(",", ".")
    try:
        hours = float(text)
        if not (1.0 <= hours <= 24.0):
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введи число от 1 до 24. Например: `6` или `7.5`")
        return

    await state.update_data(sprint_hours_per_day=hours)
    await state.set_state(SprintStates.awaiting_tasks)
    await message.answer(
        f"✅ Capacity: *{hours} ч/день*\n\n"
        "Отправь список задач — каждую с новой строки (максимум 10):\n\n"
        "Пример:\n"
        "Фикс токенов\n"
        "Фильтрация заказов\n"
        "Nova Poshta интеграция"
    )


@router.message(SprintStates.awaiting_tasks)
async def handle_sprint_tasks(message: Message, state: FSMContext, user=None):
    """
    Validate the task list, run sprint_planner_node, and display the plan.

    :param message: Message containing newline-separated task descriptions.
    :param state: The current FSM context with sprint_hours_per_day stored.
    :param user: Injected User object from UserMiddleware.
    :return: None
    """
    raw = message.text or ""
    tasks = [line.strip() for line in raw.splitlines() if line.strip()]

    if not tasks:
        await message.answer("⚠️ Список задач пустой. Напиши задачи, каждую с новой строки.")
        return

    if len(tasks) > 10:
        await message.answer(
            f"⚠️ Слишком много задач ({len(tasks)}). Максимум 10 за один спринт.\n" "Сократи список и попробуй снова."
        )
        return

    data = await state.get_data()
    hours_per_day: float = data.get("sprint_hours_per_day", 8.0)
    user_id = message.from_user.id
    project_id = user.active_project_id if user else None

    progress = await message.answer(f"⏳ Оцениваю {len(tasks)} задач...")

    result = await run_sprint_agent(
        user_id=user_id,
        project_id=project_id,
        hours_per_day=hours_per_day,
        tasks=tasks,
    )

    sprint_plan = result.get("sprint_plan")
    if sprint_plan:
        await state.set_state(None)
        await state.update_data(last_sprint_plan=sprint_plan, last_sprint_hours=hours_per_day)
        keyboard = sprint_result_keyboard()
    else:
        await state.clear()
        keyboard = None

    await progress.edit_text(
        result.get("formatted_response", "❌ Не удалось сформировать план."),
        reply_markup=keyboard,
    )
