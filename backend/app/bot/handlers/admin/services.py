"""Admin handlers: service management."""

from typing import Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message as TelegramMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import schedule_main_menu_return, send_clean_menu
from app.bot.keyboards.inline import (
    get_cancel_keyboard,
    get_service_edit_keyboard,
    get_service_list_keyboard,
    get_service_management_keyboard,
)
from app.bot.states.booking import AddServiceStates
from app.models.user import User
from app.services.service_management_service import ServiceManagementService

router = Router(name="admin-services")


@router.callback_query(F.data == "admin:manage_services")
async def manage_services_menu(
    callback: CallbackQuery,
    _: Callable[[str], str],
):
    """Show services management menu."""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.title"),
        reply_markup=get_service_management_keyboard(_),
    )
    await callback.answer()


@router.callback_query(F.data == "service:list")
async def list_services(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
):
    """Show list of services."""
    service_mgmt = ServiceManagementService(session)
    services = await service_mgmt.get_all_active_services()

    if not services:
        await send_clean_menu(
            callback=callback,
            text=_("service_management.no_services"),
            reply_markup=get_service_management_keyboard(_),
        )
        await callback.answer()
        return

    text = _("service_management.title") + "\n\n"
    for service in services:
        text += f"• {service.get_name(user.language)} ({service.duration_minutes} min)\n"

    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_service_list_keyboard(services, user.language, _),
    )
    await callback.answer()


@router.callback_query(F.data == "service:add")
async def add_service_start(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Start adding new service."""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.enter_name"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.update_data(source_language=user.language)
    await state.set_state(AddServiceStates.entering_name_pl)
    await callback.answer()


@router.message(AddServiceStates.entering_name_pl)
async def service_name_entered(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle service name input and auto-translate."""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return

    data = await state.get_data()
    source_lang = data.get("source_language", "pl")

    progress_msg = await message.answer(_("service_management.translating"))

    from app.services.translation_service import TranslationService

    translations = await TranslationService.translate_to_all_languages(
        text=message.text,
        source_lang=source_lang,
    )

    await progress_msg.delete()

    await state.update_data(
        name_pl=translations.get("pl", message.text),
        name_ru=translations.get("ru", message.text),
    )

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.confirm_translation"),
            callback_data="service:confirm_translation",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.edit_translation"),
            callback_data="service:edit_manual",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.cancel"),
            callback_data="cancel",
        )
    )

    result_text = _("service_management.translation_result").format(
        name_pl=translations.get("pl", message.text),
        name_ru=translations.get("ru", message.text),
    )

    await message.answer(result_text, reply_markup=builder.as_markup())
    await state.set_state(AddServiceStates.entering_name_ru)


@router.callback_query(F.data == "service:confirm_translation")
async def confirm_translation(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Confirm auto-translation and proceed to duration."""
    if isinstance(callback.message, TelegramMessage) and callback.bot:
        await callback.message.delete()

        await callback.bot.send_message(
            callback.message.chat.id,
            _("service_management.enter_duration"),
            reply_markup=get_cancel_keyboard(_),
        )
    await state.set_state(AddServiceStates.entering_duration)
    await callback.answer()


@router.callback_query(F.data == "service:edit_manual")
async def edit_manual(
    callback: CallbackQuery,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Manually edit translations."""
    await send_clean_menu(
        callback=callback,
        text=_("service_management.enter_name_pl"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.update_data(name_pl=None, name_ru=None)
    await state.set_state(AddServiceStates.entering_name_pl_manual)
    await callback.answer()


@router.message(AddServiceStates.entering_name_pl_manual)
async def service_name_pl_manual(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle manual Polish name input."""
    await state.update_data(name_pl=message.text)
    await message.answer(
        _("service_management.enter_name_ru"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(AddServiceStates.entering_name_ru_manual)


@router.message(AddServiceStates.entering_name_ru_manual)
async def service_name_ru_manual(
    message: TelegramMessage,
    _: Callable[[str], str],
    state: FSMContext,
):
    """Handle manual Russian name input."""
    await state.update_data(name_ru=message.text)
    await message.answer(
        _("service_management.enter_duration"),
        reply_markup=get_cancel_keyboard(_),
    )
    await state.set_state(AddServiceStates.entering_duration)


@router.message(AddServiceStates.entering_duration)
async def service_duration_entered(
    message: TelegramMessage,
    session: AsyncSession,
    _: Callable[[str], str],
    state: FSMContext,
    user: User,
):
    """Handle duration input and create service."""
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

    data = await state.get_data()

    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.create_service(
        name_pl=data["name_pl"],
        name_ru=data["name_ru"],
        duration_minutes=duration,
    )

    if service:
        await message.answer(_("service_management.service_added"))
    await state.clear()
    schedule_main_menu_return(message.bot, message.chat.id, user)


@router.callback_query(F.data.startswith("service:edit:"))
async def edit_service(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
):
    """Show service edit options."""
    if not callback.data:
        await callback.answer()
        return

    service_id = int(callback.data.split(":")[2])

    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)

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
        reply_markup=get_service_edit_keyboard(service_id, _),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service:delete:"))
async def delete_service(
    callback: CallbackQuery,
    session: AsyncSession,
    _: Callable[[str], str],
):
    """Delete service."""
    if not callback.data:
        await callback.answer()
        return

    service_id = int(callback.data.split(":")[2])

    service_mgmt = ServiceManagementService(session)
    success = await service_mgmt.delete_service(service_id)

    if not success:
        await callback.answer(_("errors.service_not_found"), show_alert=True)
        return

    await send_clean_menu(
        callback=callback,
        text=_("service_management.service_deleted"),
        reply_markup=get_service_management_keyboard(_),
    )
    await callback.answer()

