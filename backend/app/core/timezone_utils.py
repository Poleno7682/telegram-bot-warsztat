"""Timezone utilities for converting datetime to UTC"""

from datetime import datetime
from typing import Optional
import pytz

from app.config.settings import get_settings

# Cache for timezone object to avoid repeated lookups
_timezone_cache: Optional[pytz.BaseTzInfo] = None


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
    # If already UTC, return as is
    if dt.tzinfo is not None:
        # Check if it's UTC timezone
        if dt.tzinfo == pytz.UTC or str(dt.tzinfo) == 'UTC':
            return dt
        # Convert from current timezone to UTC
        return dt.astimezone(pytz.UTC)
    
    # Naive datetime - assume it's in UTC (not local timezone!)
    # This is important because when parsing ISO strings that don't have timezone,
    # we should assume they are already in UTC (since they came from UTC originally)
    return pytz.UTC.localize(dt)


def ensure_local(dt: datetime, timezone: Optional[str] = None) -> datetime:
    """
    Ensure datetime is in local timezone (convert if needed, or assume local if naive)
    
    Args:
        dt: Datetime to ensure
        timezone: Timezone name (e.g., 'Europe/Warsaw'). If None, uses settings timezone
        
    Returns:
        Datetime in local timezone (timezone-aware)
    """
    if timezone is None:
        local_tz = get_local_timezone()
    else:
        local_tz = pytz.timezone(timezone)
    
    # If already in local timezone, return as is
    if dt.tzinfo is not None:
        # Check if it's already in the target timezone
        if dt.tzinfo == local_tz or str(dt.tzinfo) == str(local_tz):
            return dt
        # Convert from current timezone to local
        return dt.astimezone(local_tz)
    
    # Naive datetime - assume it's in local timezone
    return local_tz.localize(dt)


def get_local_timezone() -> pytz.BaseTzInfo:
    """
    Get local timezone from settings with caching.
    
    This function caches the timezone object to avoid repeated lookups
    and timezone object creation, improving performance.
    
    Returns:
        Timezone object (pytz.BaseTzInfo)
        
    Example:
        >>> tz = get_local_timezone()
        >>> dt = tz.localize(datetime.now())
    """
    global _timezone_cache
    
    if _timezone_cache is None:
        settings = get_settings()
        _timezone_cache = pytz.timezone(settings.timezone)
    
    return _timezone_cache


def normalize_to_local(dt: datetime) -> datetime:
    """
    Normalize datetime to local timezone.
    
    This is a convenience wrapper around ensure_local that always uses
    the configured local timezone from settings.
    
    Args:
        dt: Datetime to normalize (can be naive or timezone-aware)
        
    Returns:
        Datetime in local timezone (timezone-aware)
        
    Example:
        >>> local_dt = normalize_to_local(some_datetime)
    """
    return ensure_local(dt)


def ensure_timezone_aware(
    dt: datetime,
    tz: Optional[pytz.BaseTzInfo] = None
) -> datetime:
    """
    Ensure datetime is timezone-aware, localizing if naive.
    
    Args:
        dt: Datetime to ensure
        tz: Timezone to use if dt is naive. If None, uses local timezone
        
    Returns:
        Timezone-aware datetime
        
    Example:
        >>> aware_dt = ensure_timezone_aware(naive_dt)
    """
    if dt.tzinfo is not None:
        return dt
    
    if tz is None:
        tz = get_local_timezone()
    
    return tz.localize(dt)

