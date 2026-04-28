from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.common import start_keyboard

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Я помогу оценивать задачи и планировать спринты.\n"
        "Для начала добавь проект.",
        reply_markup=start_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Команды бота:</b>\n\n"
        "/projects — список проектов\n"
        "/estimate — оценить задачу\n"
        "/sprint — планировщик спринта\n"
        "/stats — статистика токенов\n"
        "/cancel — выйти из текущего действия",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия.")
        return
    await state.clear()
    await message.answer("Действие отменено.")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    from config.settings import settings
    await message.answer(
        "<b>Статистика токенов:</b>\n\n"
        "Сегодня использовано: 0\n"
        f"Дневной лимит: {settings.daily_token_limit:,}\n\n"
        "В этом месяце: 0\n"
        f"Месячный лимит: {settings.monthly_token_limit:,}",
        parse_mode="HTML",
    )
