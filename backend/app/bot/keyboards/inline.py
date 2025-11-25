"""Inline keyboards for the bot"""

from typing import List, Callable
from datetime import datetime, date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.service import Service
from app.config.settings import get_settings


# Language display names mapping
LANGUAGE_NAMES = {
    "pl": "🇵🇱 Polski",
    "ru": "🇷🇺 Русский",
}


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Get language selection keyboard using supported languages from config"""
    builder = InlineKeyboardBuilder()
    
    settings = get_settings()
    supported_languages = settings.supported_languages_list
    
    # Create buttons for each supported language
    buttons = []
    for lang_code in supported_languages:
        display_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
        buttons.append(
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"lang:{lang_code}"
            )
        )
    
    # Add buttons in rows of 2
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        builder.row(*row)
    
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
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.user_settings"),
            callback_data="menu:user_settings"
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
    
    # Admin can also create bookings
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.new_booking"),
            callback_data="menu:new_booking"
        )
    )
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
            text=_("menu.admin.calendar"),
            callback_data="calendar:menu"
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
            text=_("menu.main.user_settings"),
            callback_data="menu:user_settings"
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
    
    # Mechanic can also create bookings
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.new_booking"),
            callback_data="menu:new_booking"
        )
    )
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
            text=_("menu.mechanic.calendar"),
            callback_data="calendar:menu"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.mechanic.add_service"),
            callback_data="service:add"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("menu.main.user_settings"),
            callback_data="menu:user_settings"
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
    language: str = "pl",
    _: Callable[[str], str] | None = None
) -> InlineKeyboardMarkup:
    """
    Get services selection keyboard
    
    Args:
        services: List of services
        language: Language code
        _: Translation function (optional)
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
    
    # Add back button
    back_text = _("common.back") if _ else "⬅️ Wstecz / Назад"
    builder.row(
        InlineKeyboardButton(
            text=back_text,
            callback_data="menu:main"
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


def get_user_management_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get user management keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("user_management.add_user"),
            callback_data="admin:add_user"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_management.remove_user"),
            callback_data="admin:remove_user"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_mechanic_management_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get mechanic management keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("user_management.add_mechanic"),
            callback_data="admin:add_mechanic"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_management.remove_mechanic"),
            callback_data="admin:remove_mechanic"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_service_management_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get service management keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.add_service"),
            callback_data="service:add"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.list_services"),
            callback_data="service:list"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_service_list_keyboard(
    services: List[Service],
    language: str,
    _: Callable[[str], str]
) -> InlineKeyboardMarkup:
    """
    Get service list keyboard for editing/deleting
    
    Args:
        services: List of services
        language: Language code
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    for service in services:
        name = service.get_name(language)
        builder.row(
            InlineKeyboardButton(
                text=f"{name} ({service.duration_minutes} min)",
                callback_data=f"service:edit:{service.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="admin:manage_services"
        )
    )
    
    return builder.as_markup()


def get_service_edit_keyboard(
    service_id: int,
    _: Callable[[str], str]
) -> InlineKeyboardMarkup:
    """
    Get service edit keyboard
    
    Args:
        service_id: Service ID
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.edit_service"),
            callback_data=f"service:update:{service_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("service_management.delete_service"),
            callback_data=f"service:delete:{service_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="service:list"
        )
    )
    
    return builder.as_markup()


def get_settings_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get settings management keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("settings.work_hours"),
            callback_data="settings:work_hours"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("settings.time_step"),
            callback_data="settings:time_step"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("settings.buffer_time"),
            callback_data="settings:buffer_time"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_calendar_keyboard(
    _: Callable[[str], str],
    language: str,
    available_dates: List[date]
) -> InlineKeyboardMarkup:
    """
    Get calendar navigation keyboard limited to dates with bookings
    """
    from app.services.time_service import TimeService
    
    builder = InlineKeyboardBuilder()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    for target_date in available_dates:
        if target_date == today:
            label = _("calendar.today")
        elif target_date == tomorrow:
            label = _("calendar.tomorrow")
        else:
            label = TimeService.format_date(target_date, language)
        
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"calendar:day:{target_date.isoformat()}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_user_settings_keyboard(
    _: Callable[[str], str],
    show_reminders: bool = False
) -> InlineKeyboardMarkup:
    """
    Get user settings keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("user_settings.change_language"),
            callback_data="user_settings:change_language"
        )
    )
    if show_reminders:
        builder.row(
            InlineKeyboardButton(
                text=_("user_settings.reminders_button"),
                callback_data="user_settings:reminders"
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:main"
        )
    )
    
    return builder.as_markup()


def get_reminder_settings_keyboard(
    reminder_3h_enabled: bool,
    reminder_1h_enabled: bool,
    reminder_30m_enabled: bool,
    _: Callable[[str], str]
) -> InlineKeyboardMarkup:
    """Keyboard for reminder preferences"""
    builder = InlineKeyboardBuilder()
    
    def status(enabled: bool) -> str:
        return _("user_settings.reminders_on") if enabled else _("user_settings.reminders_off")
    
    builder.row(
        InlineKeyboardButton(
            text=_("user_settings.reminders_3h").format(status=status(reminder_3h_enabled)),
            callback_data="user_settings:toggle_reminder:3h"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_settings.reminders_1h").format(status=status(reminder_1h_enabled)),
            callback_data="user_settings:toggle_reminder:1h"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("user_settings.reminders_30m").format(status=status(reminder_30m_enabled)),
            callback_data="user_settings:toggle_reminder:30m"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=_("common.back"),
            callback_data="menu:user_settings"
        )
    )
    
    return builder.as_markup()


def get_cancel_keyboard(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """
    Get cancel keyboard
    
    Args:
        _: Translation function
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=_("common.cancel"),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()

