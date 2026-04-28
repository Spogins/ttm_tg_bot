from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.common import projects_keyboard, start_keyboard
from bot.states.states import ProjectStates

router = Router()


@router.message(Command("projects"))
async def cmd_projects(message: Message):
    # Реальные данные подключаются в задаче 3
    await message.answer(
        "У вас пока нет проектов.",
        reply_markup=start_keyboard(),
    )


@router.callback_query(F.data == "add_project")
async def cb_add_project(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProjectStates.awaiting_file)
    await callback.message.answer(
        "Отправьте файл структуры проекта (JSON)."
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_file)
async def handle_project_file(message: Message, state: FSMContext):
    # Обработка файла — Phase 2
    await state.set_state(ProjectStates.awaiting_name)
    await message.answer("Введите название проекта:")


@router.message(ProjectStates.awaiting_name)
async def handle_project_name(message: Message, state: FSMContext):
    # Сохранение в БД — Phase 2
    await state.clear()
    await message.answer(f"Проект «{message.text}» добавлен.")
