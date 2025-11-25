"""Calendar handlers for admins and mechanics"""

from datetime import date, timedelta
from typing import Callable, List

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.booking import BookingRepository
from app.services.time_service import TimeService
from app.bot.keyboards.inline import get_calendar_keyboard
from app.bot.handlers.common import send_clean_menu

router = Router(name="calendar")


async def _get_available_calendar_dates(
    booking_repo: BookingRepository,
    days_ahead: int = 6
) -> List[date]:
    """Get list of dates with bookings within the next days_ahead range"""
    today = date.today()
    available_dates: List[date] = []
    
    for offset in range(0, days_ahead + 1):
        target_date = today + timedelta(days=offset)
        bookings = await booking_repo.get_by_date(target_date)
        if bookings:
            available_dates.append(target_date)
    
    return available_dates


@router.callback_query(F.data == "calendar:menu")
async def show_calendar_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Display calendar navigation buttons"""
    if user.role not in (UserRole.ADMIN, UserRole.MECHANIC):
        await callback.answer(_("errors.permission_denied"), show_alert=True)
        return
    
    booking_repo = BookingRepository(session)
    available_dates = await _get_available_calendar_dates(booking_repo)
    
    text = (
        _("calendar.title") + "\n\n" + _("calendar.select_day")
        if available_dates
        else _("calendar.no_available_days")
    )
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_calendar_keyboard(_, user.language, available_dates)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("calendar:day:"))
async def show_calendar_day(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Show bookings for selected day"""
    if not callback.data:
        await callback.answer()
        return
    
    if user.role not in (UserRole.ADMIN, UserRole.MECHANIC):
        await callback.answer(_("errors.permission_denied"), show_alert=True)
        return
    
    try:
        parts = callback.data.split(":")
        date_str = parts[2]
        target_date = date.fromisoformat(date_str)
    except ValueError:
        await callback.answer(_("errors.invalid_input"), show_alert=True)
        return
    
    booking_repo = BookingRepository(session)
    bookings = await booking_repo.get_by_date(target_date)
    available_dates = await _get_available_calendar_dates(booking_repo)
    
    date_text = TimeService.format_date(target_date, user.language)
    
    if not bookings:
        text = _("calendar.no_bookings").format(date=date_text)
    else:
        text_lines = [_("calendar.day_overview").format(date=date_text), ""]
        for booking in bookings:
            mechanic_name = (
                booking.mechanic.full_name
                if booking.mechanic else _("calendar.unassigned")
            )
            status_key = f"calendar.status.{booking.status.value}"
            status_text = _(status_key)
            text_lines.append(
                _("calendar.entry").format(
                    time=TimeService.format_time(booking.booking_date),
                    service=booking.service.get_name(user.language),
                    client=booking.client_name,
                    phone=booking.client_phone,
                    mechanic=mechanic_name,
                    status=status_text
                )
            )
            text_lines.append("")
        text = "\n".join(text_lines).strip()
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_calendar_keyboard(_, user.language, available_dates)
    )
    await callback.answer()

