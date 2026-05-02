"""
Handlers for task estimation and sprint planning commands.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.states import EstimationStates

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
    await message.answer(
        "Опишите задачу, которую нужно оценить.\n"
        "Можно голосовым сообщением или текстом."
    )


@router.message(EstimationStates.awaiting_task)
async def handle_task_description(message: Message, state: FSMContext):
    """
    Acknowledge the task description; agent estimation wired in Phase 3.

    :param message: The incoming message containing the task description.
    :param state: The current FSM context.
    :return: None
    """
    # agent integration is planned for phase 3
    await state.set_state(EstimationStates.confirming)
    await message.answer(
        f"Задача принята: «{message.text}»\n\n"
        "Оценка агентом будет доступна в Phase 3."
    )


@router.message(Command("sprint"))
async def cmd_sprint(message: Message):
    """
    Placeholder for the sprint planner, available in Phase 3.

    :param message: The incoming message object.
    :return: None
    """
    await message.answer("Планировщик спринта будет доступен в Phase 3.")
