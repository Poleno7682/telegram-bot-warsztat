"""Booking handlers - creating and managing bookings"""

from typing import Callable, cast
from aiogram import Router, F
from aiogram.types import Message as TelegramMessage, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.user import User
from app.services.booking_service import BookingService
from app.services.time_service import TimeService
from app.services.service_management_service import ServiceManagementService
from app.bot.states.booking import BookingStates
from app.bot.keyboards.inline import (
    get_services_keyboard,
    get_dates_keyboard,
    get_times_keyboard,
    get_cancel_keyboard
)

router = Router(name="booking")


@router.callback_query(F.data == "menu:new_booking")
async def start_new_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Start new booking flow"""
    from app.bot.handlers.common import send_clean_menu
    
    # Get all active services
    service_mgmt = ServiceManagementService(session)
    services = await service_mgmt.get_all_active_services()
    
    if not services:
        await send_clean_menu(
            callback=callback,
            text=_("service_management.no_services"),
            reply_markup=get_cancel_keyboard(_)
        )
        await callback.answer()
        return
    
    # Show services with clean menu
    await send_clean_menu(
        callback=callback,
        text=_("booking.create.select_service"),
        reply_markup=get_services_keyboard(services, user.language, _)
    )
    await state.set_state(BookingStates.selecting_service)
    await callback.answer()


@router.callback_query(BookingStates.selecting_service, F.data.startswith("service:"))
async def service_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle service selection"""
    if not callback.data:
        await callback.answer()
        return
    
    service_id = int(callback.data.split(":")[1])
    
    # Save service ID
    await state.update_data(service_id=service_id)
    
    # Get available dates
    time_service = TimeService(session)
    dates = await time_service.get_available_dates()
    
    # Show dates
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_date"),
            reply_markup=get_dates_keyboard(dates, user.language)
        )
    await state.set_state(BookingStates.selecting_date)
    await callback.answer()


@router.callback_query(BookingStates.selecting_date, F.data.startswith("date:"))
async def date_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle date selection"""
    if not callback.data:
        await callback.answer()
        return
    
    date_str = callback.data.split(":")[1]
    target_date = datetime.fromisoformat(date_str).date()
    
    # Get data
    data = await state.get_data()
    service_id = data.get("service_id")
    
    if not service_id or not isinstance(service_id, int):
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.unknown"))
        await state.clear()
        await callback.answer()
        return
    
    # Get service
    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)
    
    if not service:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.service_not_found"))
        await state.clear()
        await callback.answer()
        return
    
    # Calculate available time slots
    time_service = TimeService(session)
    available_times = await time_service.calculate_available_slots(
        target_date,
        service.duration_minutes
    )
    
    if not available_times:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("booking.create.no_available_slots"))
        await callback.answer()
        return
    
    # Save date
    await state.update_data(booking_date=date_str)
    
    # Show times
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_time"),
            reply_markup=get_times_keyboard(available_times, user.language)
        )
    await state.set_state(BookingStates.selecting_time)
    await callback.answer()


@router.callback_query(BookingStates.selecting_time, F.data.startswith("time:"))
async def time_selected(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle time selection"""
    if not callback.data:
        await callback.answer()
        return
    
    time_str = callback.data.split(":")[1]
    
    # Save time
    await state.update_data(booking_time=time_str)
    
    # Ask for car brand
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(_("booking.create.enter_car_brand"))
    await state.set_state(BookingStates.entering_car_brand)
    await callback.answer()


@router.message(BookingStates.entering_car_brand)
async def car_brand_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car brand input"""
    await state.update_data(car_brand=message.text)
    await message.answer(_("booking.create.enter_car_model"))
    await state.set_state(BookingStates.entering_car_model)


@router.message(BookingStates.entering_car_model)
async def car_model_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car model input"""
    await state.update_data(car_model=message.text)
    await message.answer(_("booking.create.enter_car_number"))
    await state.set_state(BookingStates.entering_car_number)


@router.message(BookingStates.entering_car_number)
async def car_number_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car number input"""
    await state.update_data(car_number=message.text)
    await message.answer(_("booking.create.enter_client_name"))
    await state.set_state(BookingStates.entering_client_name)


@router.message(BookingStates.entering_client_name)
async def client_name_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client name input"""
    await state.update_data(client_name=message.text)
    await message.answer(_("booking.create.enter_client_phone"))
    await state.set_state(BookingStates.entering_client_phone)


@router.message(BookingStates.entering_client_phone)
async def client_phone_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client phone input"""
    await state.update_data(client_phone=message.text)
    await message.answer(_("booking.create.enter_description"))
    await state.set_state(BookingStates.entering_description)


@router.message(BookingStates.entering_description)
async def description_entered(
    message: TelegramMessage,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle description input and create booking"""
    if not message.text:
        await message.answer(_("errors.invalid_input"))
        return
    
    description = message.text
    
    # Get all data
    data = await state.get_data()
    service_id = data.get("service_id")
    
    if not service_id:
        await message.answer(_("errors.unknown"))
        await state.clear()
        return
    
    # Show translating message
    trans_msg = await message.answer(_("booking.create.translating"))
    
    # Create booking
    booking_service = BookingService(session)
    booking_datetime = datetime.fromisoformat(data["booking_time"])
    
    booking, msg = await booking_service.create_booking(
        creator_telegram_id=user.telegram_id,
        service_id=service_id,
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        description=description,
        language=user.language,
        booking_datetime=booking_datetime
    )
    
    # Delete translating message
    await trans_msg.delete()
    
    if booking:
        # Format confirmation message
        time_service = TimeService(session)
        details = _("booking.confirm.details").format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(user.language),
            date=time_service.format_date(booking.booking_date.date(), user.language),
            time=time_service.format_time(booking.booking_date),
            description=booking.get_description(user.language)
        )
        
        await message.answer(details)
        await message.answer(_("booking.confirm.success"))
        
        # Notify all mechanics using NotificationService
        if message.bot:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(session, message.bot)
            await notification_service.notify_mechanics_new_booking(booking)
    else:
        await message.answer(_("booking.confirm.error") + f"\n{msg}")
    
    # Clear state
    await state.clear()


@router.callback_query(F.data == "menu:my_bookings")
async def show_my_bookings(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show user's bookings"""
    from app.repositories.booking import BookingRepository
    from app.models.booking import BookingStatus
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_creator(user.id)
    
    if not bookings:
        if isinstance(callback.message, TelegramMessage):
            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(
                    text=_("common.back"),
                    callback_data="menu:main"
                )
            )
            await callback.message.edit_text(
                _("booking.my_bookings.no_bookings"),
                reply_markup=cast(InlineKeyboardMarkup, keyboard.as_markup())
            )
        await callback.answer()
        return
    
    # Format bookings list
    text = _("booking.my_bookings.title") + "\n\n"
    
    from app.services.time_service import TimeService
    time_service = TimeService(session)
    
    for booking in bookings:
        status_emoji = {
            BookingStatus.PENDING: "⏳",
            BookingStatus.ACCEPTED: "✅",
            BookingStatus.REJECTED: "❌",
            BookingStatus.CANCELLED: "🚫"
        }.get(booking.status, "❓")
        
        text += f"{status_emoji} {time_service.format_date(booking.booking_date.date(), user.language)} "
        text += f"{time_service.format_time(booking.booking_date)}\n"
        text += f"   🛠️ {booking.service.get_name(user.language)}\n"
        text += f"   🚗 {booking.car_brand} {booking.car_model}\n"
        if booking.status == BookingStatus.ACCEPTED and booking.mechanic:
            text += f"   🔧 {booking.mechanic.get_display_name()}\n"
        text += "\n"
    
    if isinstance(callback.message, TelegramMessage):
        keyboard = InlineKeyboardBuilder()
        keyboard.row(
            InlineKeyboardButton(
                text=_("common.back"),
                callback_data="menu:main"
            )
        )
        await callback.message.edit_text(
            text,
            reply_markup=cast(InlineKeyboardMarkup, keyboard.as_markup())
        )
    await callback.answer()

