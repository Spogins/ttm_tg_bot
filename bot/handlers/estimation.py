# -*- coding: utf-8 -*-
"""
Handlers for task estimation: graph invocation, clarification loop, and save callback.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from agent.runner import run_agent
from bot.keyboards.common import estimation_keyboard
from bot.states.states import EstimationStates
from db.mongodb import estimations as estimations_db
from db.mongodb import projects as projects_db
from services.estimation_indexer import index_estimation

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


@router.message(Command("sprint"))
async def cmd_sprint(message: Message):
    """
    Inform the user that the sprint planner is available in a later phase.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer("Планировщик спринта будет доступен в следующей версии.")
