# -*- coding: utf-8 -*-
"""
Handlers for project management: listing, creating, updating, and deleting projects.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import confirm_delete_keyboard, projects_keyboard, start_keyboard
from bot.states.states import ProjectStates
from db.mongodb import projects as projects_db
from db.mongodb import users as users_db

router = Router()


@router.message(Command("projects"))
async def cmd_projects(message: Message, user=None):
    """
    Display all projects for the user with select / update / delete actions.

    :param message: The incoming message object.
    :param user: The user object, if available.
    :return: None
    """
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
        f"Ваши проекты ({len(project_list)}): ",
        reply_markup=projects_keyboard(
            [p.model_dump() for p in project_list],
            active_project_id=active_id,
        ),
    )


@router.callback_query(F.data.startswith("select_project:"))
async def cb_select_project(callback: CallbackQuery):
    """
    Set the tapped project as the user's active project and refresh the keyboard.

    :param callback: The callback query from the inline button press.
    :return: None
    """
    project_id = callback.data.split(":", 1)[1]  # limit=1 so UUIDs with colons aren't split
    user_id = callback.from_user.id

    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return

    await users_db.set_active_project(user_id, project_id)

    # re-fetch the full list and edit the keyboard in-place to reflect the new active project
    project_list = await projects_db.get_user_projects(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=projects_keyboard(
            [p.model_dump() for p in project_list],
            active_project_id=project_id,
        )
    )
    await callback.answer(f"Активный проект: {project.name}")


@router.callback_query(F.data.startswith("update_project:"))
async def cb_update_project(callback: CallbackQuery, state: FSMContext):
    """
    Enter the awaiting_update_file state so the user can upload a new structure file.

    :param callback: The callback query from the inline button press.
    :param state: The current FSM context.
    :return: None
    """
    project_id = callback.data.split(":", 1)[1]
    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return
    await state.set_state(ProjectStates.awaiting_update_file)
    await state.update_data(update_project_id=project_id)
    await callback.message.answer(
        f"Отправьте новый файл структуры для проекта «{project.name}».\n" "Индекс в Qdrant будет пересоздан."
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_update_file)
async def handle_update_file(message: Message, state: FSMContext):
    """
    Re-parse and re-index the project structure from the uploaded file or text.

    :param message: The incoming message with a document or text payload.
    :param state: The current FSM context holding the target project ID.
    :return: None
    """
    from services.indexer import delete_project_index, index_project
    from services.project_parser import parse

    data = await state.get_data()
    project_id = data.get("update_project_id")
    await state.clear()  # clear early so a crash later doesn't leave a stale state

    if not project_id:
        await message.answer("Ошибка: проект не найден. Начните заново.")
        return

    content: str | bytes = b""
    if message.document:
        file = await message.bot.get_file(message.document.file_id)
        import io

        buf = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=buf)
        content = buf.getvalue()  # raw bytes; parse() handles decoding
    elif message.text:
        content = message.text
    else:
        await message.answer("Отправьте файл или текстовое описание.")
        return

    msg = await message.answer("Пересоздаю индекс...")
    parsed = parse(content)

    await delete_project_index(project_id)
    count = await index_project(project_id, parsed)
    await projects_db.update_project(
        project_id,
        tech_stack=parsed.tech_stack,
        structure_raw=parsed.raw,
        files_indexed=count,
    )

    await msg.edit_text(
        f"Структура обновлена.\n" f"Файлов в индексе: {count}\n" f"Технологии: {', '.join(parsed.tech_stack) or '—'}"
    )


@router.callback_query(F.data.startswith("delete_project:"))
async def cb_delete_project(callback: CallbackQuery):
    """
    Show a confirmation prompt before permanently deleting the project.

    :param callback: The callback query from the inline button press.
    :return: None
    """
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
    """
    Delete the project from MongoDB and its Qdrant vector index.

    :param callback: The callback query from the confirmation button press.
    :return: None
    """
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
    """
    Dismiss the delete-confirmation message without taking action.

    :param callback: The callback query from the cancel button press.
    :return: None
    """
    await callback.message.delete()
    await callback.answer("Удаление отменено.")


@router.callback_query(F.data == "add_project")
async def cb_add_project(callback: CallbackQuery, state: FSMContext):
    """
    Start the new-project flow by entering the awaiting_file state.

    :param callback: The callback query from the add-project button press.
    :param state: The current FSM context.
    :return: None
    """
    await state.set_state(ProjectStates.awaiting_file)
    await callback.message.answer(
        "Отправьте файл структуры проекта (JSON или TXT).\n" "Или напишите описание стека текстом."
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_file)
async def handle_project_file(message: Message, state: FSMContext):
    """
    Store the uploaded file or text in FSM data and ask for a project name.

    :param message: The incoming message with a document or text payload.
    :param state: The current FSM context.
    :return: None
    """
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
    """
    Store the project name and prompt for an optional description.

    :param message: The incoming message containing the project name.
    :param state: The current FSM context holding the uploaded file or text content.
    :return: None
    """
    await state.update_data(project_name=message.text.strip())
    await state.set_state(ProjectStates.awaiting_description)
    await message.answer(
        "Кратко опишите проект: назначение, архитектурные особенности, "
        "что важно учитывать при оценке задач.\n\n"
        "Или отправьте /skip чтобы пропустить."
    )


@router.message(ProjectStates.awaiting_description)
async def handle_project_description(message: Message, state: FSMContext):
    """
    Create and index the project with the optional description provided.

    :param message: The incoming message with a description text or /skip command.
    :param state: The current FSM context holding the file and project name.
    :return: None
    """
    from services.indexer import index_project
    from services.project_parser import parse

    text = (message.text or "").strip()
    description = "" if text == "/skip" else text

    data = await state.get_data()
    await state.clear()  # clear early so a crash later doesn't leave a stale state
    name = data["project_name"]

    content: str | bytes = b""
    if "file_id" in data:
        import io

        file = await message.bot.get_file(data["file_id"])
        buf = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=buf)
        content = buf.getvalue()  # raw bytes; parse() handles decoding
    elif "text_content" in data:
        content = data["text_content"]

    parsed = parse(content)
    project = await projects_db.create_project(
        user_id=message.from_user.id,
        name=name,
        description=description,
        tech_stack=parsed.tech_stack,
        structure_raw=parsed.raw,
    )
    # set as active immediately so subsequent /estimate commands pick up the new project
    await users_db.set_active_project(message.from_user.id, project.project_id)

    msg = await message.answer(f"Проект «{name}» создан. Индексирую структуру...")
    count = await index_project(project.project_id, parsed, description=description)
    await msg.edit_text(
        f"Проект «{name}» создан и проиндексирован.\n"
        f"Файлов в индексе: {count}\n"
        f"Технологии: {', '.join(parsed.tech_stack) or '—'}"
    )
