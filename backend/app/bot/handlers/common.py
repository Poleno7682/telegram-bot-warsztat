"""Common handlers - main menu and navigation"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import Callable

from app.models.user import User, UserRole
from app.bot.keyboards.inline import (
    get_main_menu_keyboard,
    get_admin_menu_keyboard,
    get_mechanic_menu_keyboard
)

router = Router(name="common")


async def show_main_menu(message: Message, user: User):
    """
    Show main menu based on user role
    
    Args:
        message: Message to reply to
        user: User object
    """
    from app.core.i18n import get_text
    
    def _(key: str, **kwargs) -> str:
        return get_text(key, user.language, **kwargs)
    
    # Determine menu based on role
    if user.role == UserRole.ADMIN:
        menu_text = _("menu.admin.title")
        keyboard = get_admin_menu_keyboard(_)
    elif user.role == UserRole.MECHANIC:
        menu_text = _("menu.mechanic.title")
        keyboard = get_mechanic_menu_keyboard(_)
    else:
        menu_text = _("menu.main.title")
        keyboard = get_main_menu_keyboard(_)
    
    # Send or edit message
    if message.from_user:
        await message.answer(menu_text, reply_markup=keyboard)
    else:
        await message.edit_text(menu_text, reply_markup=keyboard)


@router.message(Command("menu"))
async def cmd_menu(message: Message, user: User):
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
    await show_main_menu(callback.message, user)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, user: User):
    """
    Handle cancel callback
    
    Args:
        callback: Callback query
        user: User object
    """
    from app.core.i18n import get_text
    
    text = get_text("common.cancel", user.language)
    await callback.message.edit_text(text)
    
    # Show main menu
    await show_main_menu(callback.message, user)
    await callback.answer()

