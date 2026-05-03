# -*- coding: utf-8 -*-
"""
Reminder scheduler: background asyncio task that sends actual-hours reminders.
"""
import asyncio

from aiogram import Bot
from loguru import logger

from bot.keyboards.common import actual_hours_keyboard
from db.mongodb.estimations import get_pending_reminders, mark_reminder_sent


async def reminder_scheduler(bot: Bot) -> None:
    """
    Check for pending reminders every hour and send them via the bot.

    Runs indefinitely as a background asyncio task. Each estimation is wrapped
    in its own try/except so one failure does not abort the others.

    :param bot: The aiogram Bot instance used to send messages.
    :return: None (runs forever until cancelled)
    """
    while True:
        await asyncio.sleep(3600)
        try:
            pending = await get_pending_reminders()
        except Exception as e:
            logger.error(f"reminder_scheduler: DB error: {e}")
            continue
        for est in pending:
            try:
                await bot.send_message(
                    chat_id=est.user_id,
                    text=(f"⏱ Задача завершена?\n\n" f"*{est.task[:100]}*\n\n" f"Сколько реально заняло?"),
                    parse_mode="Markdown",
                    reply_markup=actual_hours_keyboard(est.estimation_id),
                )
                await mark_reminder_sent(est.estimation_id)
                logger.info(f"reminder_scheduler: sent reminder for {est.estimation_id}")
            except Exception as e:
                logger.error(f"reminder_scheduler: failed for {est.estimation_id}: {e}")
