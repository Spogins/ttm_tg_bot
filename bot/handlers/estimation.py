# -*- coding: utf-8 -*-
"""
Handlers for task estimation: graph invocation, clarification loop, and save callback.
"""
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from loguru import logger

from agent.runner import run_agent, run_sprint_agent
from bot.keyboards.common import estimation_keyboard, sprint_result_keyboard
from bot.states.states import EstimationStates, SprintStates
from db.mongodb import estimations as estimations_db
from db.mongodb import projects as projects_db
from services.estimation_indexer import index_estimation, update_actual_hours
from services.sprint_exporter import generate_sprint_markdown

router = Router()


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext):
    """
    Enter the awaiting_task state and prompt the user to describe their task.

    :param message: The incoming message object.
    :param state: The current FSM context.
    :return: None
    """
    await state.set_state(EstimationStates.awaiting_task)
    await message.answer("Опишите задачу, которую нужно оценить.\n" "Можно голосовым сообщением или текстом.")


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
    user_id = message.from_user.id
    project_id = user.active_project_id if user else None

    # send progress indicator while the graph runs
    progress = await message.answer("⏳ Анализирую задачу...")

    result = await run_agent(user_id, message.text or "", project_id=project_id)
    response_text = result.get("formatted_response", "")

    if result.get("clarification_needed"):
        # task is vague; stay in clarifying state and wait for user's answer
        await state.set_state(EstimationStates.clarifying)
        await progress.edit_text(response_text)

    elif result.get("estimation") is not None:
        # store estimation data in FSM so the save callback can access it
        await state.update_data(
            pending_estimation=result["estimation"],
            pending_task=message.text or "",
            pending_project_id=project_id,
        )
        await state.set_state(EstimationStates.confirming)
        await progress.edit_text(response_text, reply_markup=estimation_keyboard())

    else:
        # stub responses (project mgmt, sprint, fallback) — nothing to confirm
        await state.clear()
        await progress.edit_text(response_text)


@router.callback_query(F.data == "estimation:save")
async def cb_save_estimation(callback: CallbackQuery, state: FSMContext):
    """
    Persist the pending estimation to MongoDB and index it in Qdrant.

    :param callback: The callback query from the save button.
    :param state: The current FSM context holding the pending estimation.
    :return: None
    """
    data = await state.get_data()
    estimation = data.get("pending_estimation")
    task = data.get("pending_task", "")
    project_id = data.get("pending_project_id")

    if not estimation:
        await callback.answer("Нет данных для сохранения.", show_alert=True)
        return

    user_id = callback.from_user.id
    project = await projects_db.get_project(project_id) if project_id else None

    saved = await estimations_db.save_estimation(
        user_id=user_id,
        task=task,
        total_hours=estimation["total_hours"],
        complexity=estimation["complexity"],
        tech_stack=project.tech_stack if project else [],
        # subtasks become the breakdown dict: name → hours
        breakdown={s["name"]: s["hours"] for s in estimation["subtasks"]},
        project_id=project_id,
        project_name=project.name if project else "",
        reminder_at=datetime.now(timezone.utc) + timedelta(hours=36),
    )

    try:
        await index_estimation(saved)  # vectorise for future similarity search
    except Exception as e:
        logger.warning(f"Qdrant indexing failed for estimation {saved.estimation_id}: {e}")

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)  # remove action buttons
    await callback.answer("✅ Оценка сохранена!")
    await callback.message.answer(f"Оценка сохранена. ID: `{saved.estimation_id}`")


@router.callback_query(F.data == "estimation:adjust")
async def cb_adjust_estimation(callback: CallbackQuery, state: FSMContext):
    """
    Re-enter awaiting_task so the user can refine the task description.

    :param callback: The callback query from the adjust button.
    :param state: The current FSM context.
    :return: None
    """
    await state.set_state(EstimationStates.awaiting_task)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Уточните описание задачи:")
    await callback.answer()


@router.callback_query(F.data == "estimation:details")
async def cb_details_estimation(callback: CallbackQuery, state: FSMContext):
    """
    Show the raw subtask breakdown from the pending estimation.

    :param callback: The callback query from the details button.
    :param state: The current FSM context holding the pending estimation.
    :return: None
    """
    data = await state.get_data()
    estimation = data.get("pending_estimation")

    if not estimation:
        await callback.answer("Нет данных.", show_alert=True)
        return

    lines = ["*Детализация подзадач:*", ""]
    for s in estimation["subtasks"]:
        lines.append(f"• {s['name']} — *{s['hours']}h*")

    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith("actual:"))
async def cb_actual_hours_prompt(callback: CallbackQuery, state: FSMContext):
    """
    Store the estimation_id and enter awaiting_actual_hours state.

    :param callback: The callback query from the actual-hours button.
    :param state: The current FSM context.
    :return: None
    """
    estimation_id = callback.data.split(":", 1)[1]
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
async def cmd_sprint(message: Message, state: FSMContext):
    """
    Enter sprint planning: ask for daily capacity in hours.

    :param message: The incoming /sprint command message.
    :param state: The current FSM context.
    :return: None
    """
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
