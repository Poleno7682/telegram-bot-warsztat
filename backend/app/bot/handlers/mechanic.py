"""Mechanic handlers - handling booking requests"""

from typing import Callable, cast
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message as TelegramMessage, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, LANGUAGE_UNSET
from app.services.booking_service import BookingService
from app.services.time_service import TimeService
from app.services.notification_service import NotificationService
from app.bot.keyboards.inline import get_dates_keyboard, get_booking_actions_keyboard
from app.bot.handlers.common import safe_callback_answer

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
        # Notify using NotificationService
        if callback.bot and isinstance(callback.message, TelegramMessage) and callback.message.text:
            notification_service = NotificationService(session, callback.bot)
            await notification_service.notify_booking_accepted(booking, user)
            
            # Update mechanic's message
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
    else:
        await safe_callback_answer(callback, text=msg, show_alert=True)
    
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("booking:change_time:"))
async def change_booking_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Handle time change request by mechanic"""
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    booking_id = int(callback.data.split(":")[2])
    
    # Get available dates
    time_service = TimeService(session)
    dates = await time_service.get_available_dates()
    
    # Show dates selection
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            _("booking.create.select_date"),
            reply_markup=get_dates_keyboard(dates, user.language if (user.language and user.language != LANGUAGE_UNSET) else "pl")
        )
    
    # Note: In production, use FSM state to store booking_id for time change flow
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
    
    booking_id = int(callback.data.split(":")[2])
    
    # Confirm time
    booking_service = BookingService(session)
    booking, msg = await booking_service.confirm_proposed_time(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        if callback.bot and isinstance(callback.message, TelegramMessage) and booking.mechanic:
            notification_service = NotificationService(session, callback.bot)
            await notification_service.notify_booking_accepted(booking, booking.mechanic)
            
            await callback.message.edit_text(_("booking.confirm.success"))
    else:
        await safe_callback_answer(callback, text=msg, show_alert=True)
    
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
    from app.config.settings import get_settings
    settings = get_settings()
    language = user.language if (user.language and user.language != LANGUAGE_UNSET) else (settings.supported_languages_list[0] if settings.supported_languages_list else "pl")
    
    time_service = TimeService(session)
    text = _("booking.pending.title") + f" (1/{len(bookings)})\n\n"
    text += _("booking.confirm.details").format(
        brand=booking.car_brand,
        model=booking.car_model,
        number=booking.car_number,
        client_name=booking.client_name,
        client_phone=booking.client_phone,
        service=booking.service.get_name(language),
        date=TimeService.format_date(booking.booking_date, language),
        time=TimeService.format_time(booking.booking_date),
        description=booking.get_description(language)
    )
    
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
    """Show mechanic's confirmed bookings"""
    from app.repositories.booking import BookingRepository
    from app.models.booking import BookingStatus
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_mechanic(user.id)
    
    # Filter only confirmed bookings
    confirmed_bookings = [b for b in bookings if b.status == BookingStatus.ACCEPTED]
    
    if not confirmed_bookings:
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
    
    # Format bookings list
    text = _("booking.mechanic.my_bookings_title") + "\n\n"
    
    # Get language with fallback
    from app.config.settings import get_settings
    settings = get_settings()
    language = user.language if (user.language and user.language != LANGUAGE_UNSET) else (settings.supported_languages_list[0] if settings.supported_languages_list else "pl")
    
    for booking in confirmed_bookings:
        text += f"✅ {TimeService.format_date(booking.booking_date, language)} "
        text += f"{TimeService.format_time(booking.booking_date)}\n"
        text += f"   🛠️ {booking.service.get_name(language)}\n"
        text += f"   🚗 {booking.car_brand} {booking.car_model}\n"
        text += f"   👤 {booking.client_name}\n"
        text += "\n"
    
    if isinstance(callback.message, TelegramMessage):
        await callback.message.edit_text(
            text,
            reply_markup=cast(InlineKeyboardMarkup, InlineKeyboardBuilder().row(
                InlineKeyboardButton(
                    text=_("common.back"),
                    callback_data="menu:main"
                )
            ).as_markup())
        )
    await safe_callback_answer(callback)

