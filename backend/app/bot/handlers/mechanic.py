"""Mechanic handlers - handling booking requests"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.booking_service import BookingService
from app.services.time_service import TimeService
from app.services.notification_service import NotificationService
from app.bot.keyboards.inline import get_dates_keyboard

router = Router(name="mechanic")


@router.callback_query(F.data.startswith("booking:accept:"))
async def accept_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: callable
):
    """Handle booking acceptance by mechanic"""
    booking_id = int(callback.data.split(":")[2])
    
    # Accept booking
    booking_service = BookingService(session)
    booking, msg = await booking_service.accept_booking(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        notification_service = NotificationService(session, callback.bot)
        await notification_service.notify_booking_accepted(booking, user)
        
        # Update mechanic's message
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ {_('booking.actions.accept')}"
        )
    else:
        await callback.answer(msg, show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("booking:reject:"))
async def reject_booking(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: callable
):
    """Handle booking rejection by mechanic"""
    booking_id = int(callback.data.split(":")[2])
    
    # Reject booking
    booking_service = BookingService(session)
    booking, msg = await booking_service.reject_booking(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        notification_service = NotificationService(session, callback.bot)
        await notification_service.notify_booking_rejected(booking, user)
        
        # Update mechanic's message
        await callback.message.edit_text(
            callback.message.text + f"\n\n❌ {_('booking.actions.reject')}"
        )
    else:
        await callback.answer(msg, show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("booking:change_time:"))
async def change_booking_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: callable
):
    """Handle time change request by mechanic"""
    booking_id = int(callback.data.split(":")[2])
    
    # Get available dates
    time_service = TimeService(session)
    dates = await time_service.get_available_dates()
    
    # Show dates selection
    await callback.message.edit_text(
        _("booking.create.select_date"),
        reply_markup=get_dates_keyboard(dates, user.language)
    )
    
    # Note: In production, use FSM state to store booking_id for time change flow
    await callback.answer()


@router.callback_query(F.data.startswith("booking:confirm:"))
async def confirm_proposed_time(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: callable
):
    """Handle time confirmation by creator"""
    booking_id = int(callback.data.split(":")[2])
    
    # Confirm time
    booking_service = BookingService(session)
    booking, msg = await booking_service.confirm_proposed_time(booking_id, user.telegram_id)
    
    if booking:
        # Notify using NotificationService
        notification_service = NotificationService(session, callback.bot)
        await notification_service.notify_booking_accepted(booking, booking.mechanic)
        
        await callback.message.edit_text(_("booking.confirm.success"))
    else:
        await callback.answer(msg, show_alert=True)
    
    await callback.answer()

