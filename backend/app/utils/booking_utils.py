"""Booking utilities - Helper functions for booking-related operations"""

from datetime import date
from typing import List, Dict, Callable
from collections import defaultdict

from app.models.booking import Booking
from app.core.timezone_utils import normalize_to_local


def format_booking_details(
    booking: Booking,
    language: str,
    translate: Callable[[str], str]
) -> str:
    """
    Format booking details into a human-readable string.
    
    This function centralizes the booking details formatting logic,
    ensuring consistency across the application.
    
    Args:
        booking: Booking instance (must have service relation loaded)
        language: Language code for formatting
        translate: Translation function (i18n getter)
        
    Returns:
        Formatted booking details string
        
    Example:
        >>> def _(key: str) -> str:
        ...     return get_text(key, language)
        >>> details = format_booking_details(booking, "pl", _)
    """
    from app.utils.date_formatter import DateFormatter
    
    return translate("booking.confirm.details").format(
        brand=booking.car_brand,
        model=booking.car_model,
        number=booking.car_number,
        client_name=booking.client_name,
        client_phone=booking.client_phone,
        service=booking.service.get_name(language),
        date=DateFormatter.format_date(booking.booking_date, language),
        time=DateFormatter.format_time(booking.booking_date),
        description=booking.get_description(language) or translate("booking.create.no_description")
    )


def filter_future_bookings(bookings: List[Booking]) -> List[Booking]:
    """
    Filter bookings to include only future ones (not in the past).
    
    This utility eliminates repetitive filtering logic across handlers.
    
    Args:
        bookings: List of booking instances
        
    Returns:
        List of future bookings (sorted by booking_date)
        
    Example:
        >>> future = filter_future_bookings(all_bookings)
    """
    from datetime import datetime, timezone
    
    now_utc = datetime.now(timezone.utc)
    future_bookings = []
    
    for booking in bookings:
        # Ensure booking_date is timezone-aware
        booking_date_utc = booking.booking_date
        if booking_date_utc.tzinfo is None:
            from app.core.timezone_utils import ensure_utc
            booking_date_utc = ensure_utc(booking_date_utc)
        else:
            # Convert to UTC for comparison
            booking_date_utc = booking_date_utc.astimezone(timezone.utc)
        
        if booking_date_utc >= now_utc:
            future_bookings.append(booking)
    
    # Sort by booking_date
    future_bookings.sort(key=lambda b: b.booking_date)
    
    return future_bookings


def group_bookings_by_date(bookings: List[Booking]) -> Dict[date, List[Booking]]:
    """
    Group bookings by date (in local timezone).
    
    This utility helps organize bookings for calendar views.
    
    Args:
        bookings: List of booking instances
        
    Returns:
        Dictionary mapping date to list of bookings for that date
        
    Example:
        >>> bookings_by_date = group_bookings_by_date(bookings)
        >>> for date, day_bookings in bookings_by_date.items():
        ...     print(f"{date}: {len(day_bookings)} bookings")
    """
    bookings_by_date = defaultdict(list)
    
    for booking in bookings:
        # Normalize to local timezone and extract date
        booking_date_local = normalize_to_local(booking.booking_date)
        booking_date = booking_date_local.date()
        bookings_by_date[booking_date].append(booking)
    
    return dict(bookings_by_date)

