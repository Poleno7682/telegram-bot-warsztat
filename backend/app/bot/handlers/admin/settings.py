"""Admin handlers: system settings management."""

from typing import Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message as TelegramMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_clean_menu
from app.bot.keyboards.inline import get_cancel_keyboard, get_settings_keyboard
from app.bot.states.booking import SettingsStates
from app.services.settings_management_service import SettingsManagementService

router = Router(name="admin-settings")


@router.callback_query(F.data == "admin:settings")
async def settings_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    _: Callable[[str], str],
):
    """Show settings menu."""
    settings_mgmt = SettingsManagementService(session)
    settings = await settings_mgmt.get_settings()

    text = f"""
{_("settings.title")}

{_("settings.work_hours")}: {settings.work_start_time.strftime('%H:%M')} - {settings.work_end_time.strftime('%H:%M')}
{_("settings.time_step")}: {settings.time_step_minutes} min
{_("settings.buffer_time")}: {settings.buffer_time_minutes} min
"""

    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_settings_keyboard(_),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:work_hours")
async def update_work_hours_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start updating work hours."""
    await send_clean_menu(
        callback=callback,
        text=_("settings.work_start"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(SettingsStates.updating_work_start)
    await callback.answer()


@router.message(SettingsStates.updating_work_start)
async def work_start_entered(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle work start time input."""
    from datetime import datetime

    if not message.text:
        await message.answer(_("settings.invalid_time"))
        return

    try:
        work_start = datetime.strptime(message.text.strip(), "%H:%M").time()
        await state.update_data(work_start=work_start)
        await message.answer(_("settings.work_end"))
        await state.set_state(SettingsStates.updating_work_end)
    except ValueError:
        await message.answer(_("settings.invalid_time"))


@router.message(SettingsStates.updating_work_end)
async def work_end_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle work end time input and update settings."""
    from datetime import datetime

    if not message.text:
        await message.answer(_("settings.invalid_time"))
        return

    try:
        work_end = datetime.strptime(message.text.strip(), "%H:%M").time()
        data = await state.get_data()

        settings_mgmt = SettingsManagementService(session)
        await settings_mgmt.update_work_hours(
            start_time=data["work_start"],
            end_time=work_end
        )
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("settings.invalid_time"))


@router.callback_query(F.data == "settings:time_step")
async def update_time_step_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start updating time step."""
    await send_clean_menu(
        callback=callback,
        text=_("settings.step_minutes"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(SettingsStates.updating_time_step)
    await callback.answer()


@router.message(SettingsStates.updating_time_step)
async def time_step_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle time step input and update settings."""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return

    try:
        time_step = int(message.text.strip())
        if time_step <= 0:
            raise ValueError()

        settings_mgmt = SettingsManagementService(session)
        await settings_mgmt.update_time_step(time_step)
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("errors.invalid_input"))


@router.callback_query(F.data == "settings:buffer_time")
async def update_buffer_time_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start updating buffer time."""
    await send_clean_menu(
        callback=callback,
        text=_("settings.buffer_minutes"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(SettingsStates.updating_buffer_time)
    await callback.answer()


@router.message(SettingsStates.updating_buffer_time)
async def buffer_time_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle buffer time input and update settings."""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return

    try:
        buffer_time = int(message.text.strip())
        if buffer_time < 0:
            raise ValueError()

        settings_mgmt = SettingsManagementService(session)
        await settings_mgmt.update_buffer_time(buffer_time)
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("errors.invalid_input"))

