"""Mechanic handlers - handling booking requests"""

from typing import Callable, cast
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message as TelegramMessage, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService
from app.services.time_service import TimeService
from app.utils.user_utils import get_user_language
from app.utils.date_formatter import DateFormatter
from app.utils.booking_utils import filter_future_bookings, group_bookings_by_date, format_booking_details
from app.bot.keyboards.inline import get_dates_keyboard, get_booking_actions_keyboard, get_times_keyboard
from app.bot.handlers.common import safe_callback_answer, schedule_main_menu_return
from app.bot.states.booking import BookingStates
from aiogram.fsm.context import FSMContext
from datetime import datetime

router = Router(name="mechanic")


@router.callback_query(F.data.startswith("booking:accept:"))
async def accept_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Handle booking acceptance by mechanic"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = int(callback.data.split(":")[2])
    
    # Accept booking
    booking_service = BookingService(session)
    booking, msg = await booking_service.accept_booking(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService (includes main menu in confirmation message)
        if callback.bot and isinstance(callback.message, TelegramMessage):
            notification_service = NotificationService(session, callback.bot)
            await notification_service.notify_booking_accepted(booking, user)
            
            # Update mechanic's message if it has text
            if callback.message.text:
                await callback.message.edit_text(
                    callback.message.text + f"\n\n✅ {_('booking.actions.accept')}"
                )
    else:
        await safe_callback_answer(callback, text=msg, show_alert=True)
    
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:reject:"))
async def reject_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Handle booking rejection by mechanic"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = int(callback.data.split(":")[2])
    
    # Reject booking
    booking_service = BookingService(session)
    booking, msg = await booking_service.reject_booking(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        if callback.bot and isinstance(callback.message, TelegramMessage) and callback.message.text:
            notification_service = NotificationService(session, callback.bot)
            await notification_service.notify_booking_rejected(booking, user)
            
            # Update mechanic's message
            await callback.message.edit_text(
                callback.message.text + f"\n\n❌ {_('booking.actions.reject')}"
            )
        
        # Return to main menu
        if callback.bot and isinstance(callback.message, TelegramMessage):
            schedule_main_menu_return(callback.bot, callback.message.chat.id, user)
    else:
        await safe_callback_answer(callback, text=msg, show_alert=True)
    
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:change_time:"))
async def change_booking_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str],
    state: FSMContext
):
    """Handle time change request by mechanic"""
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
    
    # Save booking_id and service_id to state for time change flow
    await state.update_data(
        change_time_booking_id=booking_id,
        service_id=booking.service.id
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
    
    # Show dates selection
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_date"),
            reply_markup=get_dates_keyboard(dates, language)
        )
    
    # Set FSM state to handle date selection
    await state.set_state(BookingStates.selecting_date)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "mechanic:pending")
async def show_pending_bookings(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show pending bookings for mechanic"""
    from app.repositories.booking import BookingRepository
    from app.models.booking import BookingStatus
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_status(BookingStatus.PENDING)
    
    if not bookings:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(
                _("booking.pending.no_bookings"),
                reply_markup=cast(InlineKeyboardMarkup, InlineKeyboardBuilder().row(
                    InlineKeyboardButton(
                        text=_("common.back"),
                        callback_data="menu:main"
                    )
                ).as_markup())
            )
        await safe_callback_answer(callback)
        return
    
    # Show first booking
    booking = bookings[0]
    
    # Get language with fallback
    language = get_user_language(user)
    
    text = _("booking.pending.title") + f" (1/{len(bookings)})\n\n"
    text += format_booking_details(booking, language, _)
    
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            text,
            reply_markup=get_booking_actions_keyboard(booking.id, _)
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "mechanic:my_bookings")
async def show_mechanic_bookings(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show mechanic's confirmed bookings - day selection"""
    from app.repositories.booking import BookingRepository
    from app.models.booking import BookingStatus
    from datetime import date, timedelta
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_mechanic(user.id)
    
    # Filter only confirmed bookings
    confirmed_bookings = [b for b in bookings if b.status == BookingStatus.ACCEPTED]
    
    # Filter out past bookings
    future_bookings = filter_future_bookings(confirmed_bookings)
    
    if not future_bookings:
        if isinstance(callback.message, TelegramMessage):
            await callback.message.edit_text(
                _("booking.my_bookings.no_bookings"),
                reply_markup=cast(InlineKeyboardMarkup, InlineKeyboardBuilder().row(
                    InlineKeyboardButton(
                        text=_("common.back"),
                        callback_data="menu:main"
                    )
                ).as_markup())
            )
        await safe_callback_answer(callback)
        return
    
    # Group bookings by date (in local timezone)
    bookings_by_date = group_bookings_by_date(future_bookings)
    
    # Sort dates
    sorted_dates = sorted(bookings_by_date.keys())
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Create keyboard with dates
    builder = InlineKeyboardBuilder()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    for target_date in sorted_dates:
        if target_date == today:
            label = _("calendar.today")
        elif target_date == tomorrow:
            label = _("calendar.tomorrow")
        else:
            label = DateFormatter.format_date(target_date, language)
        
        # Add count of bookings for this day
        count = len(bookings_by_date[target_date])
        label += f" ({count})"
        
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"mechanic:my_bookings_day:{target_date.isoformat()}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    text = _("booking.mechanic.my_bookings_title") + "\n\n" + _("booking.mechanic.select_day")
    
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup()
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("mechanic:my_bookings_day:"))
async def show_mechanic_bookings_day(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show mechanic's confirmed bookings for selected day"""
    from app.repositories.booking import BookingRepository
    from app.models.booking import BookingStatus
    
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    # Parse date from callback
    date_str = callback.data.split(":")[2]
    target_date = datetime.fromisoformat(date_str).date()
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_mechanic(user.id)
    
    # Filter only confirmed bookings
    confirmed_bookings = [b for b in bookings if b.status == BookingStatus.ACCEPTED]
    
    # Filter out past bookings and filter by selected date
    future_bookings = filter_future_bookings(confirmed_bookings)
    
    # Filter by selected date
    day_bookings = []
    from app.core.timezone_utils import normalize_to_local
    for booking in future_bookings:
        # Convert to local timezone and check date
        booking_date_local = normalize_to_local(booking.booking_date)
        booking_date = booking_date_local.date()
        
        # Only include bookings for selected date
        if booking_date == target_date:
            day_bookings.append(booking)
    
    # Get language with fallback
    language = get_user_language(user)
    
    # Format date header
    date_header = DateFormatter.format_date(target_date, language)
    text = f"📅 {date_header}\n\n"
    
    if not day_bookings:
        text += _("booking.my_bookings.no_bookings")
    else:
        # Sort bookings by time
        day_bookings_sorted = sorted(day_bookings, key=lambda b: b.booking_date)
        
        for booking in day_bookings_sorted:
            text += f"🕐 {DateFormatter.format_time(booking.booking_date)}\n"
            text += f"🛠️ {booking.service.get_name(language)}\n"
            text += f"🚗 {booking.car_brand} {booking.car_model}\n"
            text += f"👤 {booking.client_name} 📞 {booking.client_phone}\n"
            text += "\n"
    
    # Create keyboard with back button
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="mechanic:my_bookings"
        )
    )
    
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup()
        )
    await safe_callback_answer(callback)

