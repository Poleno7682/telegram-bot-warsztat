"""Inline keyboards for the bot"""

from typing import List, Callable
from datetime import datetime, date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.service import Service


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Get language selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🇵🇱 Polski", callback_data="lang:pl"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
    )
    
    return builder.as_markup()


def get_main_menu_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get main menu keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.new_booking"),
            callback_data="menu:new_booking"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.my_bookings"),
            callback_data="menu:my_bookings"
        )
    )
    
    return builder.as_markup()


def get_admin_menu_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get admin menu keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("menu.admin.manage_users"),
            callback_data="admin:manage_users"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.admin.manage_mechanics"),
            callback_data="admin:manage_mechanics"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.admin.manage_services"),
            callback_data="admin:manage_services"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.admin.manage_settings"),
            callback_data="admin:settings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_mechanic_menu_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get mechanic menu keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("menu.mechanic.pending_bookings"),
            callback_data="mechanic:pending"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.mechanic.my_bookings"),
            callback_data="mechanic:my_bookings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.mechanic.manage_services"),
            callback_data="admin:manage_services"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_services_keyboard(
    services: List[Service],
    language: str = "pl"
) -> InlineKeyboardMarkup:
    """
    Get services selection keyboard
    
    Args:
        services: List of services
        language: Language code
    """
    builder = InlineKeyboardBuilder()
    
    for service in services:
        name = service.get_name(language)
        builder.row(
            InlineKeyboardButton(
                text=f"{name} ({service.duration_minutes} min)",
                callback_data=f"service:{service.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Anuluj / Отмена",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_dates_keyboard(
    dates: List[date],
    language: str = "pl"
) -> InlineKeyboardMarkup:
    """
    Get dates selection keyboard
    
    Args:
        dates: List of available dates
        language: Language code
    """
    from app.services.time_service import TimeService
    
    builder = InlineKeyboardBuilder()
    
    for target_date in dates:
        date_text = TimeService.format_date(target_date, language)
        builder.row(
            InlineKeyboardButton(
                text=date_text,
                callback_data=f"date:{target_date.isoformat()}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Anuluj / Отмена",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_times_keyboard(
    times: List[datetime],
    language: str = "pl"
) -> InlineKeyboardMarkup:
    """
    Get times selection keyboard
    
    Args:
        times: List of available datetime slots
        language: Language code
    """
    from app.services.time_service import TimeService
    
    builder = InlineKeyboardBuilder()
    
    # Group times by rows (3 per row)
    for i in range(0, len(times), 3):
        row_times = times[i:i+3]
        buttons = [
            InlineKeyboardButton(
                text=TimeService.format_time(t),
                callback_data=f"time:{t.isoformat()}"
            )
            for t in row_times
        ]
        builder.row(*buttons)
    
    builder.row(
        InlineKeyboardButton(
            text="❌ Anuluj / Отмена",
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_booking_actions_keyboard(
    booking_id: int,
    _: Callable[[str], str]
) -> InlineKeyboardMarkup:
    """
    Get booking actions keyboard for mechanic
    
    Args:
        booking_id: Booking ID
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("booking.actions.accept"),
            callback_data=f"booking:accept:{booking_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("booking.actions.reject"),
            callback_data=f"booking:reject:{booking_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("booking.actions.change_time"),
            callback_data=f"booking:change_time:{booking_id}"
        )
    )
    
    return builder.as_markup()


def get_confirmation_keyboard(
    booking_id: int,
    _: Callable[[str], str],
    show_change_time: bool = False
) -> InlineKeyboardMarkup:
    """
    Get confirmation keyboard
    
    Args:
        booking_id: Booking ID
        _: Translation function
        show_change_time: Show change time button
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("booking.actions.confirm_time"),
            callback_data=f"booking:confirm:{booking_id}"
        )
    )
    
    if show_change_time:
        builder.row(
            InlineKeyboardButton(
                text=_("booking.actions.propose_new_time"),
                callback_data=f"booking:user_propose_time:{booking_id}"
            )
        )
    
    return builder.as_markup()

