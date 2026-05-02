from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.common import projects_keyboard, start_keyboard, confirm_delete_keyboard
from bot.states.states import ProjectStates
from db.mongodb import users as users_db, projects as projects_db

router = Router()


@router.message(Command("projects"))
async def cmd_projects(message: Message, user=None):
    user_id = message.from_user.id
    project_list = await projects_db.get_user_projects(user_id)

    if not project_list:
        await message.answer(
            "У вас пока нет проектов.",
            reply_markup=start_keyboard(),
        )
        return

    active_id = user.active_project_id if user else None
    await message.answer(
        f"Ваши проекты ({len(project_list)}):",
        reply_markup=projects_keyboard(
            [p.model_dump() for p in project_list],
            active_project_id=active_id,
        ),
    )


@router.callback_query(F.data.startswith("select_project:"))
async def cb_select_project(callback: CallbackQuery):
    project_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await users_db.set_active_project(user_id, project_id)

    project_list = await projects_db.get_user_projects(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=projects_keyboard(
            [p.model_dump() for p in project_list],
            active_project_id=project_id,
        )
    )
    await callback.answer(f"Активный проект: {project.name}")


@router.callback_query(F.data.startswith("delete_project:"))
async def cb_delete_project(callback: CallbackQuery):
    project_id = callback.data.split(":", 1)[1]
    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return
    await callback.message.answer(
        f"Удалить проект «{project.name}»?\nЭто действие нельзя отменить.",
        reply_markup=confirm_delete_keyboard(project_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery):
    from services.indexer import delete_project_index

    project_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await delete_project_index(project_id)
    await projects_db.delete_project(project_id)

    user = await users_db.get_user(user_id)
    if user and user.active_project_id == project_id:
        await users_db.set_active_project(user_id, None)

    await callback.message.edit_text(f"Проект «{project.name}» удалён.")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cb_cancel_delete(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Удаление отменено.")


@router.callback_query(F.data == "add_project")
async def cb_add_project(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProjectStates.awaiting_file)
    await callback.message.answer(
        "Отправьте файл структуры проекта (JSON или TXT).\n"
        "Или напишите описание стека текстом."
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_file)
async def handle_project_file(message: Message, state: FSMContext):
    if message.document:
        await state.update_data(file_id=message.document.file_id, file_name=message.document.file_name)
    elif message.text:
        await state.update_data(text_content=message.text)
    else:
        await message.answer("Отправьте файл или текстовое описание.")
        return

    await state.set_state(ProjectStates.awaiting_name)
    await message.answer("Введите название проекта:")


@router.message(ProjectStates.awaiting_name)
async def handle_project_name(message: Message, state: FSMContext):
    from services.project_parser import parse
    from services.indexer import index_project

    name = message.text.strip()
    data = await state.get_data()
    await state.clear()

    content = b""
    if "file_id" in data:
        bot = message.bot
        file = await bot.get_file(data["file_id"])
        import io
        buf = io.BytesIO()
        await bot.download_file(file.file_path, destination=buf)
        content = buf.getvalue()
    elif "text_content" in data:
        content = data["text_content"]

    parsed = parse(content)
    project = await projects_db.create_project(
        user_id=message.from_user.id,
        name=name,
        tech_stack=parsed.tech_stack,
        structure_raw=parsed.raw,
    )
    await users_db.set_active_project(message.from_user.id, project.project_id)

    msg = await message.answer(f"Проект «{name}» создан. Индексирую структуру...")
    count = await index_project(project.project_id, parsed)
    await msg.edit_text(
        f"Проект «{name}» создан и проиндексирован.\n"
        f"Файлов в индексе: {count}\n"
        f"Технологии: {', '.join(parsed.tech_stack) or '—'}"
    )
