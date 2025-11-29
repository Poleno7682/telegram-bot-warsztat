"""Booking handlers - creating and managing bookings"""

from typing import Callable, cast
from aiogram import Router, F
from aiogram.types import Message as TelegramMessage, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.user import User, LANGUAGE_UNSET
from app.services.booking_service import BookingService
from app.services.time_service import TimeService
from app.services.service_management_service import ServiceManagementService
from app.services.notification_service import NotificationService
from app.bot.states.booking import BookingStates
from app.utils.user_utils import get_user_language
from app.utils.date_formatter import DateFormatter
from app.utils.validators import validate_phone
from app.utils.callback_utils import parse_callback_data
from app.utils.booking_utils import format_booking_details
from app.bot.keyboards.inline import (
    get_services_keyboard,
    get_dates_keyboard,
    get_times_keyboard,
    get_cancel_keyboard,
    get_skip_keyboard
)
from app.bot.handlers.common import safe_callback_answer, _build_menu_payload

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
        await safe_callback_answer(callback)
        return
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Show services with clean menu
    await send_clean_menu(
        callback=callback,
        text=_("booking.create.select_service"),
        reply_markup=get_services_keyboard(services, language, _)
    )
    await state.set_state(BookingStates.selecting_service)
    await safe_callback_answer(callback)


@router.callback_query(BookingStates.selecting_service, F.data.startswith("service:"))
async def service_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle service selection"""
    service_id = parse_callback_data(callback.data, "service:", index=1)
    if service_id is None:
        await safe_callback_answer(callback)
        return
    
    # Get service to get duration
    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)
    
    if not service:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.service_not_found"))
        await state.clear()
        await safe_callback_answer(callback)
        return
    
    # Save service ID
    await state.update_data(service_id=service_id)
    
    # Get available dates (filtered by available slots)
    time_service = TimeService(session)
    dates = await time_service.get_available_dates(service.duration_minutes)
    
    # Check if there are any available dates
    if not dates:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("booking.create.no_available_dates"))
        await safe_callback_answer(callback)
        return
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Show dates
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_date"),
            reply_markup=get_dates_keyboard(dates, language)
        )
    await state.set_state(BookingStates.selecting_date)
    await safe_callback_answer(callback)


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
        await safe_callback_answer(callback)
        return
    
    if not callback.data or not callback.data.startswith("date:"):
        await safe_callback_answer(callback)
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
        await safe_callback_answer(callback)
        return
    
    # Get service
    service_mgmt = ServiceManagementService(session)
    service = await service_mgmt.get_service_by_id(service_id)
    
    if not service:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.service_not_found"))
        await state.clear()
        await safe_callback_answer(callback)
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
        await safe_callback_answer(callback)
        return
    
    # Save date
    await state.update_data(booking_date=date_str)
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Show times
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_time"),
            reply_markup=get_times_keyboard(available_times, language, _)
        )
    await state.set_state(BookingStates.selecting_time)
    await safe_callback_answer(callback)


@router.callback_query(BookingStates.selecting_time, F.data.startswith("time:"))
async def time_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle time selection"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    if not callback.data or not callback.data.startswith("time:"):
        await safe_callback_answer(callback)
        return
    # Extract time string after "time:" prefix (use split with maxsplit=1 to preserve colons in ISO format)
    time_str = callback.data.split(":", 1)[1]
    booking_datetime = datetime.fromisoformat(time_str)
    
    # Ensure booking_datetime is timezone-aware and in local timezone
    # Store time in local timezone (not UTC) as requested
    from app.core.timezone_utils import ensure_local
    booking_datetime = ensure_local(booking_datetime)
    
    # Get data from state
    data = await state.get_data()
    change_time_booking_id = data.get("change_time_booking_id")
    
    # Check if this is time change flow
    if change_time_booking_id:
        # Get booking to check who is proposing (mechanic or user)
        from app.repositories.booking import BookingRepository
        booking_repo = BookingRepository(session)
        booking = await booking_repo.get_with_relations(change_time_booking_id)
        
        if not booking:
            if isinstance(callback.message, TelegramMessage):
                await callback.message.edit_text(_("errors.unknown"))
            await state.clear()
            await safe_callback_answer(callback)
            return
        
        booking_service = BookingService(session)
        
        # Check if user is mechanic or creator
        from app.models.user import UserRole
        is_mechanic = user.role == UserRole.MECHANIC
        is_creator = booking.creator_id == user.id
        
        if is_mechanic:
            # Mechanic proposing new time
            booking, msg = await booking_service.propose_new_time(
                change_time_booking_id,
                user.telegram_id,
                booking_datetime
            )
            
            if booking:
                # Notify creator
                if callback.bot and isinstance(callback.message, TelegramMessage):
                    notification_service = NotificationService(session, callback.bot)
                    await notification_service.notify_time_change_proposed(booking, user)
                    
                    await callback.message.edit_text(_("booking.actions.change_time") + ": " + _("booking.confirm.time_proposed"))
                
                # Return to main menu
                if callback.bot and isinstance(callback.message, TelegramMessage):
                    from app.bot.handlers.common import schedule_main_menu_return
                    schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
            else:
                if isinstance(callback.message, TelegramMessage):
                    await callback.message.edit_text(_("errors.unknown") + f"\n{msg}")
        elif is_creator:
            # User (creator) proposing new time
            booking, msg = await booking_service.propose_new_time_by_user(
                change_time_booking_id,
                user.telegram_id,
                booking_datetime
            )
            
            if booking:
                # Notify mechanic if exists
                if callback.bot and isinstance(callback.message, TelegramMessage) and booking.mechanic:
                    notification_service = NotificationService(session, callback.bot)
                    # Notify mechanic about user's time proposal
                    await notification_service.notify_user_time_change_proposed(booking, user)
                    
                    await callback.message.edit_text(_("booking.actions.propose_new_time") + ": " + _("booking.confirm.time_proposed"))
                
                # Return to main menu
                if callback.bot and isinstance(callback.message, TelegramMessage):
                    from app.bot.handlers.common import schedule_main_menu_return
                    schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
            else:
                if isinstance(callback.message, TelegramMessage):
                    await callback.message.edit_text(_("errors.unknown") + f"\n{msg}")
        else:
            if isinstance(callback.message, TelegramMessage):
                await callback.message.edit_text(_("errors.permission_denied"))
        
        await state.clear()
        await safe_callback_answer(callback)
        return
    
    # Normal booking creation flow
    # Save time
    await state.update_data(booking_time=time_str)
    
    # Ask for car brand and model together
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.enter_car_brand_model"),
            reply_markup=get_cancel_keyboard(_)
        )
    await state.set_state(BookingStates.entering_car_brand_model)
    await safe_callback_answer(callback)


@router.message(BookingStates.entering_car_brand_model)
async def car_brand_model_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car brand and model input"""
    if not message.text:
        await message.answer(
            _("errors.invalid_input"),
            reply_markup=get_cancel_keyboard(_)
        )
        return
    
    # Parse brand and model from input
    # Try to split by common separators or use first word as brand, rest as model
    text = message.text.strip()
    
    # Try splitting by comma, dash, or space
    if ',' in text:
        parts = [p.strip() for p in text.split(',', 1)]
    elif ' - ' in text:
        parts = [p.strip() for p in text.split(' - ', 1)]
    elif ' — ' in text:
        parts = [p.strip() for p in text.split(' — ', 1)]
    elif '-' in text and not text.startswith('-'):
        parts = [p.strip() for p in text.split('-', 1)]
    else:
        # Split by first space
        parts = text.split(' ', 1)
    
    if len(parts) >= 2:
        car_brand = parts[0]
        car_model = parts[1]
    else:
        # If only one word, use it as brand, model is empty
        car_brand = parts[0] if parts else text
        car_model = ""
    
    await state.update_data(car_brand=car_brand, car_model=car_model)
    await message.answer(
        _("booking.create.enter_car_number"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_car_number)


@router.message(BookingStates.entering_car_number)
async def car_number_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle car number input"""
    await state.update_data(car_number=message.text)
    await message.answer(
        _("booking.create.enter_client_name"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_client_name)


@router.message(BookingStates.entering_client_name)
async def client_name_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client name input"""
    await state.update_data(client_name=message.text)
    await message.answer(
        _("booking.create.enter_client_phone"),
        reply_markup=get_cancel_keyboard(_)
    )
    await state.set_state(BookingStates.entering_client_phone)


@router.message(BookingStates.entering_client_phone)
async def client_phone_entered(message: TelegramMessage, _: Callable[[str], str], state: FSMContext):
    """Handle client phone input"""
    # Validate phone number - only digits
    if not message.text:
        await message.answer(
            _("booking.create.phone_invalid"),
            reply_markup=get_cancel_keyboard(_)
        )
        return
    
    # Validate phone number
    is_valid, phone = validate_phone(message.text)
    if not is_valid:
        await message.answer(
            _("booking.create.phone_invalid"),
            reply_markup=get_cancel_keyboard(_)
        )
        return
    
    await state.update_data(client_phone=phone)
    await message.answer(
        _("booking.create.enter_description"),
        reply_markup=get_skip_keyboard(_)
    )
    await state.set_state(BookingStates.entering_description)


@router.callback_query(F.data == "booking:skip_description", BookingStates.entering_description)
async def skip_description(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle skipping description"""
    if not isinstance(callback.message, TelegramMessage):
        await safe_callback_answer(callback)
        return
    
    # Set empty description
    description = ""
    
    # Get all data
    data = await state.get_data()
    service_id = data.get("service_id")
    
    if not service_id:
        await callback.message.edit_text(_("errors.unknown"))
        await state.clear()
        await safe_callback_answer(callback)
        return
    
    # Show translating message
    trans_msg = await callback.message.answer(_("booking.create.translating"))
    
    # Create booking
    booking_service = BookingService(session)
    booking_datetime = datetime.fromisoformat(data["booking_time"])
    
    # Log before ensure_local to see original time
    import structlog
    log = structlog.get_logger()
    log.info(
        "Parsed booking time from state",
        time_str=data["booking_time"],
        parsed_datetime=str(booking_datetime),
        parsed_minute=booking_datetime.minute
    )
    
    # Ensure booking_datetime is timezone-aware and in local timezone
    # Store time in local timezone (not UTC) as requested
    from app.core.timezone_utils import ensure_local
    booking_datetime = ensure_local(booking_datetime)
    
    log.info(
        "After ensure_local",
        datetime=str(booking_datetime),
        minute=booking_datetime.minute
    )
    
    # Get language with fallback for booking creation
    booking_language = get_user_language(user)
    
    booking, msg = await booking_service.create_booking(
        creator_telegram_id=user.telegram_id,
        service_id=service_id,
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        description=description,
        language=booking_language,
        booking_datetime=booking_datetime
    )
    
    # Delete translating message
    await trans_msg.delete()
    
    if booking:
        # Format confirmation message
        language = get_user_language(user)
        details = format_booking_details(booking, language, _)
        
        await callback.message.edit_text(details)
        await callback.message.answer(_("booking.confirm.success"))
        
        # Notify all mechanics using NotificationService
        if callback.bot:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(session, callback.bot)
            await notification_service.notify_mechanics_new_booking(booking)
    else:
        await callback.message.edit_text(_("booking.confirm.error") + f"\n{msg}")
    
    # Clear state
    await state.clear()
    await safe_callback_answer(callback)


@router.message(BookingStates.entering_description)
async def description_entered(
    message: TelegramMessage,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle description input and create booking"""
    # Description is optional, so empty text is allowed
    description = message.text if message.text else ""
    
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
    
    # Log before ensure_local to see original time
    import structlog
    log = structlog.get_logger()
    log.info(
        "Parsed booking time from state",
        time_str=data["booking_time"],
        parsed_datetime=str(booking_datetime),
        parsed_minute=booking_datetime.minute
    )
    
    # Ensure booking_datetime is timezone-aware and in local timezone
    # Store time in local timezone (not UTC) as requested
    from app.core.timezone_utils import ensure_local
    booking_datetime = ensure_local(booking_datetime)
    
    log.info(
        "After ensure_local",
        datetime=str(booking_datetime),
        minute=booking_datetime.minute
    )
    
    # Get language with fallback for booking creation
    booking_language = get_user_language(user)
    
    booking, msg = await booking_service.create_booking(
        creator_telegram_id=user.telegram_id,
        service_id=service_id,
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        car_number=data["car_number"],
        client_name=data["client_name"],
        client_phone=data["client_phone"],
        description=description,
        language=booking_language,
        booking_datetime=booking_datetime
    )
    
    # Delete translating message
    await trans_msg.delete()
    
    if booking:
        # Format confirmation message
        language = get_user_language(user)
        details = format_booking_details(booking, language, _)
        
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


@router.callback_query(F.data.startswith("booking:user_propose_time:"))
async def user_propose_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle user proposing new time for booking"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = int(callback.data.split(":")[2])
    
    # Get booking to get service duration (with relations loaded)
    from app.repositories.booking import BookingRepository
    booking_repo = BookingRepository(session)
    booking = await booking_repo.get_with_relations(booking_id)
    
    if not booking or not booking.service:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.unknown"))
        await safe_callback_answer(callback)
        return
    
    # Verify user is the creator
    if booking.creator_id != user.id:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.permission_denied"))
        await safe_callback_answer(callback)
        return
    
    # Save booking_id and service_id to state for time change flow
    await state.update_data(
        change_time_booking_id=booking_id,
        service_id=booking.service_id
    )
    
    # Get available dates (filtered by available slots)
    time_service = TimeService(session)
    dates = await time_service.get_available_dates(booking.service.duration_minutes)
    
    # Check if there are any available dates
    if not dates:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("booking.create.no_available_dates"))
        await safe_callback_answer(callback)
        return
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Show dates
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_date"),
            reply_markup=get_dates_keyboard(dates, language)
        )
    await state.set_state(BookingStates.selecting_date)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:confirm:"))
async def confirm_proposed_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Handle time confirmation by creator"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = parse_callback_data(callback.data, "booking:confirm:", index=2)
    if booking_id is None:
        await safe_callback_answer(callback)
        return
    
    # Confirm time
    booking_service = BookingService(session)
    booking, msg = await booking_service.confirm_proposed_time(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        if callback.bot and isinstance(callback.message, TelegramMessage):
            notification_service = NotificationService(session, callback.bot)
            
            # Notify mechanic that user confirmed the proposed time
            if booking.mechanic:
                await notification_service.notify_time_confirmed(booking, user)
            
            await callback.message.edit_text(_("booking.confirm.success"))
        
        # Return to main menu
        if callback.bot and isinstance(callback.message, TelegramMessage):
            from app.bot.handlers.common import schedule_main_menu_return
            schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
    else:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(_("errors.unknown") + f"\n{msg}")
    
    await safe_callback_answer(callback)


@router.callback_query(F.data == "booking:cancel")
async def cancel_booking_callback(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle booking cancellation from callback - clear state and return to main menu"""
    # Clear FSM state
    await state.clear()
    
    # Return to main menu
    menu_text, keyboard = _build_menu_payload(user)
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.booking_cancelled") + "\n\n" + menu_text,
            reply_markup=keyboard
        )
    
    await safe_callback_answer(callback)


# Note: Cancel button is available via callback_query handler above
# Users can click the cancel button on any step to cancel booking creation


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
        await safe_callback_answer(callback)
        return
    
    # Format bookings list
    text = _("booking.my_bookings.title") + "\n\n"
    
    language = get_user_language(user)
    
    for booking in bookings:
        status_emoji = {
            BookingStatus.PENDING: "⏳",
            BookingStatus.ACCEPTED: "✅",
            BookingStatus.REJECTED: "❌",
            BookingStatus.CANCELLED: "🚫"
        }.get(booking.status, "❓")
        
        text += f"{status_emoji} {DateFormatter.format_date(booking.booking_date, language)} "
        text += f"{DateFormatter.format_time(booking.booking_date)}\n"
        text += f"   🛠️ {booking.service.get_name(language)}\n"
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
    await safe_callback_answer(callback)

