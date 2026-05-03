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


@router.callback_query(F.data == "project:noop")
async def cb_project_noop(callback: CallbackQuery):
    """
    Silently acknowledge taps on the active-project checkmark button.

    :param callback: Callback query with 'project:noop' data.
    :return: None
    """
    await callback.answer()


@router.callback_query(F.data.startswith("select_project:"))
async def cb_select_project(callback: CallbackQuery):
    """
    Set the tapped project as the user's active project and refresh the keyboard.

    :param callback: The callback query from the inline button press.
    :return: None
    """
    project_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return
    if project.user_id != user_id:
        await callback.answer("Этот проект вам не принадлежит.", show_alert=True)
        return

    await users_db.set_active_project(user_id, project_id)

    project_list = await projects_db.get_user_projects(user_id)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=projects_keyboard(
                [p.model_dump() for p in project_list],
                active_project_id=project_id,
            )
        )
    except Exception:
        pass  # "message is not modified" on stale callbacks — safe to ignore
    await callback.answer(f"Активный проект: {project.name}")


@router.callback_query(F.data.startswith("update_project:"))
async def cb_update_project(callback: CallbackQuery, state: FSMContext):
    """
    Show the project card and ask for a new description before updating.

    :param callback: The callback query from the inline button press.
    :param state: The current FSM context.
    :return: None
    """
    project_id = callback.data.split(":", 1)[1]
    project = await projects_db.get_project(project_id)
    if not project:
        await callback.answer("Проект не найден.", show_alert=True)
        return
    if project.user_id != callback.from_user.id:
        await callback.answer("Этот проект вам не принадлежит.", show_alert=True)
        return

    await state.set_state(ProjectStates.awaiting_update_description)
    await state.update_data(update_project_id=project_id)

    stack = ", ".join(project.tech_stack) if project.tech_stack else "—"
    updated = project.updated_at.strftime("%d.%m.%Y %H:%M")
    description_line = f"📝 {project.description}\n" if project.description else ""
    await callback.message.answer(
        f"<b>📁 {project.name}</b>\n"
        f"{description_line}"
        f"🛠 Стек: {stack}\n"
        f"🕐 Обновлён: {updated}\n\n"
        "Введите новое описание проекта или /skip чтобы оставить текущее.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ProjectStates.awaiting_update_description)
async def handle_update_description(message: Message, state: FSMContext):
    """
    Store the new description and ask for the updated tech stack.

    :param message: The incoming message with description text or /skip.
    :param state: The current FSM context holding the target project ID.
    :return: None
    """
    text = (message.text or "").strip()
    if text == "/skip":
        data = await state.get_data()
        project = await projects_db.get_project(data.get("update_project_id", ""))
        description = project.description if project else ""
        await state.update_data(update_description=description)
    else:
        await state.update_data(update_description=text)

    await state.set_state(ProjectStates.awaiting_update_stack)
    await message.answer(
        "Введите новый стек технологий через запятую:\n\n" "<code>Django, PostgreSQL, Redis, React, Docker</code>",
        parse_mode="HTML",
    )


@router.message(ProjectStates.awaiting_update_stack)
async def handle_update_stack(message: Message, state: FSMContext):
    """
    Normalize the stack via Claude, re-index the project, and update MongoDB.

    :param message: The incoming message with a tech stack list.
    :param state: The current FSM context holding project ID and description.
    :return: None
    """
    from services.indexer import delete_project_index, index_project
    from services.project_claude import extract_tech_stack
    from services.project_parser import ParsedProject

    if not message.text or not message.text.strip():
        await message.answer("Введите стек технологий текстом.")
        return

    data = await state.get_data()
    project_id = data.get("update_project_id")
    description = data.get("update_description", "")
    await state.clear()

    if not project_id:
        await message.answer("Ошибка: проект не найден. Начните заново.")
        return

    if message.text.strip() == "/skip":
        project = await projects_db.get_project(project_id)
        existing_stack = project.tech_stack if project else []
        await projects_db.update_project(project_id, description=description)
        stack_str = ", ".join(existing_stack) or "—"
        await message.answer(f"✅ Описание обновлено.\nТехнологии без изменений: {stack_str}")
        return

    msg = await message.answer("Анализирую стек через Claude ✨")
    tech_stack = await extract_tech_stack(message.text.strip(), description)
    parsed = ParsedProject(files=[], tech_stack=tech_stack, modules=[], raw={"description": description})

    await msg.edit_text("Пересоздаю индекс...")
    await delete_project_index(project_id)
    count = await index_project(project_id, parsed, description=description)
    await projects_db.update_project(
        project_id,
        description=description,
        tech_stack=parsed.tech_stack,
        structure_raw=parsed.raw,
        files_indexed=count,
    )

    await msg.edit_text(f"✅ Структура обновлена.\nТехнологии: {', '.join(parsed.tech_stack) or '—'}")


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
    if project.user_id != callback.from_user.id:
        await callback.answer("Этот проект вам не принадлежит.", show_alert=True)
        return
    await callback.message.answer(
        f"Удалить проект «{project.name}»?\nЭто действие нельзя отменить.",
        reply_markup=confirm_delete_keyboard(project_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery):
    """
    Delete the project from MongoDB and its Qdrant vector index, then show the updated list.

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
    if project.user_id != user_id:
        await callback.answer("Этот проект вам не принадлежит.", show_alert=True)
        return

    await delete_project_index(project_id)
    await projects_db.delete_project(project_id)

    user = await users_db.get_user(user_id)
    was_active = user is not None and user.active_project_id == project_id
    if was_active:
        await users_db.set_active_project(user_id, None)
    active_id = None if was_active else (user.active_project_id if user else None)

    await callback.message.edit_text(f"Проект «{project.name}» удалён.")

    project_list = await projects_db.get_user_projects(user_id)
    if project_list:
        await callback.message.answer(
            f"Ваши проекты ({len(project_list)}):",  # noqa: E231
            reply_markup=projects_keyboard(
                [p.model_dump() for p in project_list],
                active_project_id=active_id,
            ),
        )
    else:
        await callback.message.answer("Проектов больше нет.", reply_markup=start_keyboard())

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
    Start the new-project flow by asking for the project name.

    :param callback: The callback query from the add-project button press.
    :param state: The current FSM context.
    :return: None
    """
    await state.set_state(ProjectStates.awaiting_name)
    await callback.message.answer("Введите название проекта:")
    await callback.answer()


@router.message(ProjectStates.awaiting_name)
async def handle_project_name(message: Message, state: FSMContext):
    """
    Store the project name and prompt for an optional description.

    :param message: The incoming message containing the project name.
    :param state: The current FSM context.
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
    Store the description and prompt for the tech stack.

    :param message: The incoming message with a description text or /skip command.
    :param state: The current FSM context holding the project name.
    :return: None
    """
    text = (message.text or "").strip()
    description = "" if text == "/skip" else text
    await state.update_data(project_description=description)
    await state.set_state(ProjectStates.awaiting_stack)
    await message.answer(
        "Введите стек технологий через запятую:\n\n" "<code>Django, PostgreSQL, Redis, React, Docker</code>",
        parse_mode="HTML",
    )


@router.message(ProjectStates.awaiting_stack)
async def handle_project_stack(message: Message, state: FSMContext):
    """
    Normalize the stack via Claude, create the project, and index it in Qdrant.

    :param message: The incoming message with a tech stack list.
    :param state: The current FSM context holding the project name and description.
    :return: None
    """
    from services.indexer import index_project
    from services.project_claude import extract_tech_stack
    from services.project_parser import ParsedProject

    if not message.text or not message.text.strip():
        await message.answer("Введите стек технологий текстом.")
        return

    data = await state.get_data()
    await state.clear()
    name = data["project_name"]
    description = data.get("project_description", "")

    msg = await message.answer(f"Создаю проект «{name}»... Анализирую стек через Claude ✨")
    tech_stack = await extract_tech_stack(message.text.strip(), description)
    parsed = ParsedProject(files=[], tech_stack=tech_stack, modules=[], raw={"description": description})

    project = await projects_db.create_project(
        user_id=message.from_user.id,
        name=name,
        description=description,
        tech_stack=parsed.tech_stack,
        structure_raw=parsed.raw,
    )
    await users_db.set_active_project(message.from_user.id, project.project_id)

    await index_project(project.project_id, parsed, description=description)
    await msg.edit_text(
        f"✅ Проект «{name}» создан и проиндексирован.\n" f"Технологии: {', '.join(parsed.tech_stack) or '—'}"
    )
