"""Admin handlers: user management."""

from typing import Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message as TelegramMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import schedule_main_menu_return, send_clean_menu
from app.bot.keyboards.inline import get_cancel_keyboard, get_user_management_keyboard
from app.bot.states.booking import UserManagementStates
from app.core.service_factory import ServiceFactory
from app.models.user import User, UserRole

router = Router(name="admin-users")


@router.callback_query(F.data == "admin:manage_users")
async def manage_users_menu(callback: CallbackQuery, _: Callable[[str], str]):
    """Show user management menu."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.title") + "\n\n" + _("user_management.select_action"),
        reply_markup=get_user_management_keyboard(_),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_user")
async def add_user_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start adding new user."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(UserManagementStates.adding_user)
    await callback.answer()


@router.message(UserManagementStates.adding_user)
async def add_user_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    user: User,
):
    """Process adding new user."""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return

    # Get service factory from data (injected by middleware)
    service_factory = ServiceFactory(session, message.bot) if message.bot else ServiceFactory(session)
    auth_service = service_factory.get_auth_service()
    created_user = await auth_service.add_user_role(telegram_id, UserRole.USER)

    if created_user:
        await message.answer(_("user_management.user_added"))
    else:
        await message.answer(_("user_management.user_not_found"))

    await state.clear()
    schedule_main_menu_return(message.bot, message.chat.id, user)


@router.callback_query(F.data == "admin:remove_user")
async def remove_user_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start removing user."""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(UserManagementStates.removing_user)
    await callback.answer()


@router.message(UserManagementStates.removing_user)
async def remove_user_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    user: User,
):
    """Process removing user."""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return

    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return

    service_factory = ServiceFactory(session, message.bot) if message.bot else ServiceFactory(session)
    auth_service = service_factory.get_auth_service()
    success = await auth_service.remove_user_role(telegram_id)

    if success:
        await message.answer(_("user_management.user_removed"))
    else:
        await message.answer(_("user_management.user_not_found"))

    await state.clear()
    schedule_main_menu_return(message.bot, message.chat.id, user)

