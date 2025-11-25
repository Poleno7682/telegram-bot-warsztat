"""Admin handlers: mechanic management."""

from typing import Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message as TelegramMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import schedule_main_menu_return, send_clean_menu, safe_callback_answer
from app.bot.keyboards.inline import (
    get_cancel_keyboard,
    get_mechanic_management_keyboard,
)
from app.bot.states.booking import UserManagementStates
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

router = Router(name="admin-mechanics")


@router.callback_query(F.data == "admin:manage_mechanics")
async def manage_mechanics_menu(callback: CallbackQuery, _: Callable[[str], str]):
    """Show mechanic management menu."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.title") + "\n\n" + _("user_management.select_action"),
        reply_markup=get_mechanic_management_keyboard(_),
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "admin:add_mechanic")
async def add_mechanic_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start adding new mechanic."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(UserManagementStates.adding_mechanic)
    await safe_callback_answer(callback)


@router.message(UserManagementStates.adding_mechanic)
async def add_mechanic_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    user: User,
):
    """Process adding new mechanic."""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return

    auth_service = AuthService(session)
    created_mechanic = await auth_service.add_user_role(telegram_id, UserRole.MECHANIC)

    if created_mechanic:
        await message.answer(_("user_management.mechanic_added"))
    else:
        await message.answer(_("user_management.user_not_found"))

    await state.clear()
    schedule_main_menu_return(message.bot, message.chat.id, user)


@router.callback_query(F.data == "admin:remove_mechanic")
async def remove_mechanic_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start removing mechanic."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(UserManagementStates.removing_mechanic)
    await safe_callback_answer(callback)


@router.message(UserManagementStates.removing_mechanic)
async def remove_mechanic_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    user: User,
):
    """Process removing mechanic."""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return

    auth_service = AuthService(session)
    success = await auth_service.remove_user_role(telegram_id)

    if success:
        await message.answer(_("user_management.mechanic_removed"))
    else:
        await message.answer(_("user_management.user_not_found"))

    await state.clear()
    schedule_main_menu_return(message.bot, message.chat.id, user)

