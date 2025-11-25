"""Timezone utilities for converting datetime to UTC"""

from datetime import datetime
from typing import Optional
import pytz

from app.config.settings import get_settings


def to_utc(dt: datetime, timezone: Optional[str] = None) -> datetime:
    """
    Convert datetime to UTC
    
    Args:
        dt: Datetime to convert (can be naive or timezone-aware)
        timezone: Timezone name (e.g., 'Europe/Warsaw'). If None, uses settings timezone
        
    Returns:
        Datetime in UTC (timezone-aware)
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in the specified timezone
        if timezone is None:
            settings = get_settings()
            timezone = settings.timezone
        tz = pytz.timezone(timezone)
        dt = tz.localize(dt)
    
    # Convert to UTC
    return dt.astimezone(pytz.UTC)


def from_utc(dt: datetime, timezone: Optional[str] = None) -> datetime:
    """
    Convert UTC datetime to local timezone
    
    Args:
        dt: UTC datetime (timezone-aware)
        timezone: Target timezone name. If None, uses settings timezone
        
    Returns:
        Datetime in local timezone (timezone-aware)
    """
    if dt.tzinfo is None:
        # Assume it's already UTC if naive
        dt = pytz.UTC.localize(dt)
    
    if timezone is None:
        settings = get_settings()
        timezone = settings.timezone
    
    target_tz = pytz.timezone(timezone)
    return dt.astimezone(target_tz)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is in UTC (convert if needed, or assume UTC if naive)
    
    Args:
        dt: Datetime to ensure
        
    Returns:
        Datetime in UTC (timezone-aware)
    """
    return to_utc(dt)

