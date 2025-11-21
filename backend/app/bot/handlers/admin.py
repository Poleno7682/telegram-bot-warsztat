"""Admin handlers - user, mechanic, service and settings management"""

from typing import Callable, cast
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message as TelegramMessage, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.repositories.service import ServiceRepository
from app.repositories.settings import SettingsRepository
from app.bot.states.booking import AddServiceStates, UserManagementStates, SettingsStates
from app.bot.keyboards.inline import (
    get_user_management_keyboard,
    get_mechanic_management_keyboard,
    get_service_management_keyboard,
    get_service_list_keyboard,
    get_service_edit_keyboard,
    get_settings_keyboard,
    get_cancel_keyboard
)
from app.bot.handlers.common import send_clean_menu

router = Router(name="admin")


# ==================== USER MANAGEMENT ====================

@router.callback_query(F.data == "admin:manage_users")
async def manage_users_menu(callback: CallbackQuery, _: Callable[[str], str]):
    """Show user management menu"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.title") + "\n\n" + _("user_management.select_action"),
        reply_markup=get_user_management_keyboard(_)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_user")
async def add_user_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start adding new user"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(UserManagementStates.adding_user)
    await callback.answer()


@router.message(UserManagementStates.adding_user)
async def add_user_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Process adding new user"""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return
    
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return
    
    # Add user
    auth_service = AuthService(session)
    user = await auth_service.add_user_role(telegram_id, UserRole.USER)
    
    if user:
        await message.answer(_("user_management.user_added"))
    else:
        await message.answer(_("user_management.user_not_found"))
    
    await state.clear()


@router.callback_query(F.data == "admin:remove_user")
async def remove_user_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start removing user"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(UserManagementStates.removing_user)
    await callback.answer()


@router.message(UserManagementStates.removing_user)
async def remove_user_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Process removing user"""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return
    
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return
    
    # Remove user role
    auth_service = AuthService(session)
    success = await auth_service.remove_user_role(telegram_id)
    
    if success:
        await message.answer(_("user_management.user_removed"))
    else:
        await message.answer(_("user_management.user_not_found"))
    
    await state.clear()


# ==================== MECHANIC MANAGEMENT ====================

@router.callback_query(F.data == "admin:manage_mechanics")
async def manage_mechanics_menu(callback: CallbackQuery, _: Callable[[str], str]):
    """Show mechanic management menu"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.title") + "\n\n" + _("user_management.select_action"),
        reply_markup=get_mechanic_management_keyboard(_)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:add_mechanic")
async def add_mechanic_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start adding new mechanic"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(UserManagementStates.adding_mechanic)
    await callback.answer()


@router.message(UserManagementStates.adding_mechanic)
async def add_mechanic_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Process adding new mechanic"""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return
    
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return
    
    # Add mechanic
    auth_service = AuthService(session)
    user = await auth_service.add_user_role(telegram_id, UserRole.MECHANIC)
    
    if user:
        await message.answer(_("user_management.mechanic_added"))
    else:
        await message.answer(_("user_management.user_not_found"))
    
    await state.clear()


@router.callback_query(F.data == "admin:remove_mechanic")
async def remove_mechanic_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start removing mechanic"""
    await send_clean_menu(
        callback=callback,
        text=_("user_management.enter_telegram_id"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(UserManagementStates.removing_mechanic)
    await callback.answer()


@router.message(UserManagementStates.removing_mechanic)
async def remove_mechanic_process(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Process removing mechanic"""
    if not message.text:
        await message.answer(_("user_management.invalid_id"))
        return
    
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(_("user_management.invalid_id"))
        return
    
    # Remove mechanic role
    auth_service = AuthService(session)
    success = await auth_service.remove_user_role(telegram_id)
    
    if success:
        await message.answer(_("user_management.mechanic_removed"))
    else:
        await message.answer(_("user_management.user_not_found"))
    
    await state.clear()


# ==================== SERVICE MANAGEMENT ====================

@router.callback_query(F.data == "admin:manage_services")
async def manage_services_menu(
    callback: CallbackQuery,
    _: Callable[[str], str]
):
    """Show services management menu"""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.title"),
        reply_markup=get_service_management_keyboard(_)
    )
    await callback.answer()


@router.callback_query(F.data == "service:list")
async def list_services(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show list of services"""
    service_repo = ServiceRepository(session)
    services = await service_repo.get_all_active()
    
    if not services:
        await send_clean_menu(
            callback=callback,
            text=_("service_management.no_services"),
            reply_markup=get_service_management_keyboard(_)
        )
        await callback.answer()
        return
    
    text = _("service_management.title") + "\n\n"
    for service in services:
        text += f"• {service.get_name(user.language)} ({service.duration_minutes} min)\n"
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_service_list_keyboard(services, user.language, _)
    )
    await callback.answer()


@router.callback_query(F.data == "service:add")
async def add_service_start(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start adding new service"""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.enter_name"),
        reply_markup=get_cancel_keyboard(_)
    )
    # Save user's language for translation
    await state.update_data(source_language=user.language)
    await state.set_state(AddServiceStates.entering_name_pl)
    await callback.answer()


@router.message(AddServiceStates.entering_name_pl)
async def service_name_entered(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle service name input and auto-translate"""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return
    
    # Get source language
    data = await state.get_data()
    source_lang = data.get("source_language", "pl")
    
    # Show translation in progress
    progress_msg = await message.answer(_("service_management.translating"))
    
    # Import translation service
    from app.services.translation_service import TranslationService
    
    # Translate to all languages
    translations = await TranslationService.translate_to_all_languages(
        text=message.text,
        source_lang=source_lang,
        target_languages=["pl", "ru"]
    )
    
    # Delete progress message
    await progress_msg.delete()
    
    # Save translations
    await state.update_data(
        name_pl=translations.get("pl", message.text),
        name_ru=translations.get("ru", message.text)
    )
    
    # Show translation result with confirmation buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.confirm_translation"),
            callback_data="service:confirm_translation"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.edit_translation"),
            callback_data="service:edit_manual"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.cancel"),
            callback_data="cancel"
        )
    )
    
    result_text = _("service_management.translation_result").format(
        name_pl=translations.get("pl", message.text),
        name_ru=translations.get("ru", message.text)
    )
    
    await message.answer(
        result_text,
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddServiceStates.entering_name_ru)  # Reuse state for confirmation


@router.callback_query(F.data == "service:confirm_translation")
async def confirm_translation(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Confirm auto-translation and proceed to duration"""
    if isinstance(callback.message, TelegramMessage) and callback.bot:
        await callback.message.delete()
        
        await callback.bot.send_message(
            callback.message.chat.id,
            _("service_management.enter_duration"),
            reply_markup=get_cancel_keyboard(_)
        )
    await state.set_state(AddServiceStates.entering_duration)
    await callback.answer()


@router.callback_query(F.data == "service:edit_manual")
async def edit_manual(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Manually edit translations"""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.enter_name_pl"),
        reply_markup=get_cancel_keyboard(_)
    )
    # Clear auto-translated names
    await state.update_data(name_pl=None, name_ru=None)
    await state.set_state(AddServiceStates.entering_name_pl_manual)
    await callback.answer()


@router.message(AddServiceStates.entering_name_pl_manual)
async def service_name_pl_manual(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle manual Polish name input"""
    await state.update_data(name_pl=message.text)
    await message.answer(
        _("service_management.enter_name_ru"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(AddServiceStates.entering_name_ru_manual)


@router.message(AddServiceStates.entering_name_ru_manual)
async def service_name_ru_manual(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle manual Russian name input"""
    await state.update_data(name_ru=message.text)
    await message.answer(
        _("service_management.enter_duration"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(AddServiceStates.entering_duration)


@router.message(AddServiceStates.entering_duration)
async def service_duration_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle duration input and create service"""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(_("errors.invalid_input"))
        return
    
    # Get data
    data = await state.get_data()
    
    # Create service
    service_repo = ServiceRepository(session)
    
    service = await service_repo.create(
        name_pl=data["name_pl"],
        name_ru=data["name_ru"],
        duration_minutes=duration,
        is_active=True
    )
    
    await session.commit()
    
    await message.answer(_("service_management.service_added"))
    await state.clear()


@router.callback_query(F.data.startswith("service:edit:"))
async def edit_service(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show service edit options"""
    if not callback.data:
        await callback.answer()
        return
    
    service_id = int(callback.data.split(":")[2])
    
    service_repo = ServiceRepository(session)
    service = await service_repo.get_by_id(service_id)
    
    if not service:
        await callback.answer(_("errors.service_not_found"), show_alert=True)
        return
    
    text = f"""
{_("service_management.title")}

{_("common.name")}: {service.get_name(user.language)}
{_("service_management.duration")}: {service.duration_minutes} min
"""
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_service_edit_keyboard(service_id, _)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service:delete:"))
async def delete_service(
    callback: CallbackQuery,
    session: AsyncSession,
    _: Callable[[str], str]
):
    """Delete service"""
    if not callback.data:
        await callback.answer()
        return
    
    service_id = int(callback.data.split(":")[2])
    
    service_repo = ServiceRepository(session)
    service = await service_repo.get_by_id(service_id)
    
    if not service:
        await callback.answer(_("errors.service_not_found"), show_alert=True)
        return
    
    # Soft delete - mark as inactive
    service.is_active = False
    await session.commit()
    
    await send_clean_menu(
        callback=callback,
        text=_("service_management.service_deleted"),
        reply_markup=get_service_management_keyboard(_)
    )
    await callback.answer()


# ==================== SETTINGS MANAGEMENT ====================

@router.callback_query(F.data == "admin:settings")
async def settings_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    _: Callable[[str], str]
):
    """Show settings menu"""
    settings_repo = SettingsRepository(session)
    settings = await settings_repo.get_settings()
    
    text = f"""
{_("settings.title")}

{_("settings.work_hours")}: {settings.work_start_time.strftime('%H:%M')} - {settings.work_end_time.strftime('%H:%M')}
{_("settings.time_step")}: {settings.time_step_minutes} min
{_("settings.buffer_time")}: {settings.buffer_time_minutes} min
"""
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_settings_keyboard(_)
    )
    await callback.answer()


@router.callback_query(F.data == "settings:work_hours")
async def update_work_hours_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start updating work hours"""
    await send_clean_menu(
        callback=callback,
        text=_("settings.work_start"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(SettingsStates.updating_work_start)
    await callback.answer()


@router.message(SettingsStates.updating_work_start)
async def work_start_entered(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle work start time input"""
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
    state: FSMContext
):
    """Handle work end time input and update settings"""
    from datetime import datetime
    
    if not message.text:
        await message.answer(_("settings.invalid_time"))
        return
    
    try:
        work_end = datetime.strptime(message.text.strip(), "%H:%M").time()
        data = await state.get_data()
        
        # Update settings
        settings_repo = SettingsRepository(session)
        settings = await settings_repo.get_settings()
        
        settings.work_start_time = data["work_start"]
        settings.work_end_time = work_end
        
        await session.commit()
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("settings.invalid_time"))


@router.callback_query(F.data == "settings:time_step")
async def update_time_step_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start updating time step"""
    await send_clean_menu(
        callback=callback,
        text=_("settings.step_minutes"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(SettingsStates.updating_time_step)
    await callback.answer()


@router.message(SettingsStates.updating_time_step)
async def time_step_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle time step input and update settings"""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return
    
    try:
        time_step = int(message.text.strip())
        if time_step <= 0:
            raise ValueError()
        
        # Update settings
        settings_repo = SettingsRepository(session)
        settings = await settings_repo.get_settings()
        settings.time_step_minutes = time_step
        
        await session.commit()
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("errors.invalid_input"))


@router.callback_query(F.data == "settings:buffer_time")
async def update_buffer_time_start(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start updating buffer time"""
    await send_clean_menu(
        callback=callback,
        text=_("settings.buffer_minutes"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(SettingsStates.updating_buffer_time)
    await callback.answer()


@router.message(SettingsStates.updating_buffer_time)
async def buffer_time_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle buffer time input and update settings"""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return
    
    try:
        buffer_time = int(message.text.strip())
        if buffer_time < 0:
            raise ValueError()
        
        # Update settings
        settings_repo = SettingsRepository(session)
        settings = await settings_repo.get_settings()
        settings.buffer_time_minutes = buffer_time
        
        await session.commit()
        await message.answer(_("settings.settings_updated"))
        await state.clear()
    except ValueError:
        await message.answer(_("errors.invalid_input"))
