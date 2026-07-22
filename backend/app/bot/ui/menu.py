"""Main menu building blocks.

Extracted out of app.bot.handlers.common so this logic can be used both by
handlers and by app.services.notification_service without the service layer
having to import from the handlers package (see docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md, 1.1).
This module must not import anything from app.bot.handlers or app.services.
"""

import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from app.core.deferred_message_manager import get_deferred_message_manager
from app.core.i18n import get_text
from app.models.user import User, UserRole
from app.utils.user_utils import get_user_language
from app.bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_admin_menu_keyboard,
    get_mechanic_menu_keyboard,
)


def build_menu_payload(user: User) -> tuple[str, InlineKeyboardMarkup]:
    """Build menu text and keyboard for given user based on their role"""
    language = get_user_language(user)

    def _(key: str, **kwargs) -> str:
        return get_text(key, language, **kwargs)

    if user.role == UserRole.ADMIN:
        menu_text = _("menu.admin.title")
        keyboard = get_admin_menu_keyboard(_)
    elif user.role == UserRole.MECHANIC:
        menu_text = _("menu.mechanic.title")
        keyboard = get_mechanic_menu_keyboard(_)
    else:
        menu_text = _("menu.main.title")
        keyboard = get_main_menu_keyboard(_)

    return menu_text, keyboard


def schedule_main_menu_return(
    bot: Optional[Bot],
    chat_id: int,
    user: User,
    delay: float = 3.0,
):
    """
    Schedule automatic return to main menu after delay

    Uses DeferredMessageManager to prevent duplicate messages if called multiple times
    for the same chat.
    """
    if not bot:
        return

    async def _send_menu():
        menu_text, keyboard = build_menu_payload(user)
        try:
            await bot.send_message(chat_id, menu_text, reply_markup=keyboard)
        except TelegramBadRequest:
            # Ignore if message cannot be sent
            pass

    # Use deferred message manager to prevent duplicates
    manager = get_deferred_message_manager()
    asyncio.create_task(
        manager.schedule_message(
            bot=bot,
            chat_id=chat_id,
            message_func=_send_menu,
            delay=delay,
            cancel_previous=True,
        )
    )
