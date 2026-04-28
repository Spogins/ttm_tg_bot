from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.states import EstimationStates

router = Router()


@router.message(Command("estimate"))
async def cmd_estimate(message: Message, state: FSMContext):
    await state.set_state(EstimationStates.awaiting_task)
    await message.answer(
        "Опишите задачу, которую нужно оценить.\n"
        "Можно голосовым сообщением или текстом."
    )


@router.message(EstimationStates.awaiting_task)
async def handle_task_description(message: Message, state: FSMContext):
    # Агент подключается в Phase 3
    await state.set_state(EstimationStates.confirming)
    await message.answer(
        f"Задача принята: «{message.text}»\n\n"
        "Оценка агентом будет доступна в Phase 3."
    )


@router.message(Command("sprint"))
async def cmd_sprint(message: Message):
    await message.answer("Планировщик спринта будет доступен в Phase 3.")
