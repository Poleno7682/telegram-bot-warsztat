"""Common handlers - main menu and navigation"""

import asyncio
from typing import Callable, Union, Tuple

from aiogram import Router, F, Bot
from aiogram.types import Message as TelegramMessage, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from app.models.user import User, UserRole
from app.core.deferred_message_manager import get_deferred_message_manager
from app.bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_admin_menu_keyboard,
    get_mechanic_menu_keyboard
)

router = Router(name="common")


def _build_menu_payload(user: User) -> tuple[str, InlineKeyboardMarkup]:
    """Build menu text and keyboard for given user"""
    from app.core.i18n import get_text
    from app.config.settings import get_settings
    
    # Use user's language or fallback to first supported language
    if user.language:
        language = user.language
    else:
        settings = get_settings()
        language = settings.supported_languages_list[0] if settings.supported_languages_list else "pl"
    
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


async def send_clean_menu(
    callback: CallbackQuery,
    text: str,
    reply_markup,
    delete_previous: bool = True
) -> TelegramMessage | None:
    """
    Send menu message with optional deletion of previous message
    
    Args:
        callback: Callback query
        text: Message text
        reply_markup: Keyboard markup
        delete_previous: Whether to delete previous message
        
    Returns:
        Sent message or None if bot is not available
    """
    if not isinstance(callback.message, TelegramMessage) or not callback.bot:
        return None
    
    # Delete previous message if requested
    if delete_previous:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            # Message already deleted or too old
            pass
    
    # Send new message
    return await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=reply_markup
    )


def schedule_main_menu_return(
    bot: Bot | None,
    chat_id: int,
    user: User,
    delay: float = 3.0
):
    """
    Schedule automatic return to main menu after delay
    
    Uses DeferredMessageManager to prevent duplicate messages if called multiple times
    for the same chat.
    """
    if not bot:
        return
    
    async def _send_menu():
        menu_text, keyboard = _build_menu_payload(user)
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
            cancel_previous=True
        )
    )


async def show_main_menu(
    source: Union[TelegramMessage, CallbackQuery],
    user: User,
    delete_previous: bool = True
):
    """
    Show main menu based on user role
    
    Args:
        source: Message or CallbackQuery to respond to
        user: User object
        delete_previous: Whether to delete previous message (only for callbacks)
    """
    menu_text, keyboard = _build_menu_payload(user)
    
    # Handle different source types
    if isinstance(source, CallbackQuery):
        # For callback queries - delete previous and send new
        await send_clean_menu(
            callback=source,
            text=menu_text,
            reply_markup=keyboard,
            delete_previous=delete_previous
        )
    else:
        # For direct messages - just send
        await source.answer(menu_text, reply_markup=keyboard)


@router.message(Command("menu"))
async def cmd_menu(message: TelegramMessage, user: User):
    """
    Handle /menu command
    
    Args:
        message: Message from user
        user: User object (injected by middleware)
    """
    await show_main_menu(message, user)


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery, user: User):
    """
    Handle main menu callback
    
    Args:
        callback: Callback query
        user: User object
    """
    await show_main_menu(callback, user)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, user: User):
    """
    Handle cancel callback
    
    Args:
        callback: Callback query
        user: User object
    """
    # Show main menu (will delete current message and send new)
    await show_main_menu(callback, user)
    await callback.answer()

