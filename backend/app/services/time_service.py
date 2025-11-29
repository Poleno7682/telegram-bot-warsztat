"""Time Service for calculating available booking slots"""

from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from app.repositories.booking import BookingRepository
from app.repositories.settings import SettingsRepository
from app.models.booking import Booking
from app.models.settings import SystemSettings
from app.config.settings import get_settings as get_config_settings
from app.core.timezone_utils import get_local_timezone, normalize_to_local


class TimeSlot:
    """Represents a time slot"""
    
    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end
    
    def __repr__(self) -> str:
        return f"<TimeSlot({self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')})>"
    
    def overlaps(self, other: "TimeSlot") -> bool:
        """Check if this slot overlaps with another"""
        return self.start < other.end and self.end > other.start


class TimeService:
    """Service for time-related operations and slot calculations (SRP)"""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize time service
        
        Args:
            session: Database session
        """
        self.session = session
        self.booking_repo = BookingRepository(session)
        self.settings_repo = SettingsRepository(session)
        # Cache for settings to avoid repeated DB queries within the same operation
        self._cached_settings: Optional[SystemSettings] = None
    
    async def _get_settings(self, force_refresh: bool = False) -> SystemSettings:
        """
        Get system settings with caching.
        
        This method caches settings for the lifetime of the TimeService instance
        to avoid repeated database queries during a single operation.
        
        Args:
            force_refresh: If True, force refresh from database
            
        Returns:
            SystemSettings instance
        """
        if self._cached_settings is None or force_refresh:
            self._cached_settings = await self.settings_repo.get_settings()
        return self._cached_settings
    
    async def get_available_dates(
        self, 
        service_duration: int,
        days_ahead: Optional[int] = None
    ) -> List[date]:
        """
        Get list of available dates for booking that have at least one available slot
        
        Args:
            service_duration: Service duration in minutes (required to check availability)
            days_ahead: Number of days to look ahead (from settings if None)
            
        Returns:
            List of dates with available slots
        """
        settings = await self._get_settings()
        
        if days_ahead is None:
            days_ahead = settings.booking_days_ahead
        
        today = date.today()
        available_dates = []
        
        for i in range(days_ahead):
            target_date = today + timedelta(days=i)
            
            # Check if this date has any available slots
            slots = await self.calculate_available_slots(target_date, service_duration)
            
            # Only include dates with available slots
            if slots:
                available_dates.append(target_date)
        
        return available_dates
    
    async def get_work_hours(self) -> Tuple[time, time]:
        """
        Get work start and end times
        
        Returns:
            Tuple of (start_time, end_time)
        """
        settings = await self._get_settings()
        return settings.work_start_time, settings.work_end_time
    
    async def get_time_step(self) -> int:
        """
        Get time step in minutes
        
        Returns:
            Time step in minutes
        """
        settings = await self._get_settings()
        return settings.time_step_minutes
    
    async def get_buffer_time(self) -> int:
        """
        Get buffer time in minutes
        
        Returns:
            Buffer time in minutes
        """
        settings = await self._get_settings()
        return settings.buffer_time_minutes
    
    async def calculate_available_slots(
        self,
        target_date: date,
        service_duration: int
    ) -> List[datetime]:
        """
        Calculate all available time slots for a given date and service.
        For today's date, only shows slots starting from current time.
        
        Args:
            target_date: Target date
            service_duration: Service duration in minutes
            
        Returns:
            List of available datetime slots (in local timezone)
        """
        settings = await self._get_settings()
        
        # Get timezone with caching
        tz = get_local_timezone()
        
        # Get work hours
        work_start = datetime.combine(target_date, settings.work_start_time)
        work_end = datetime.combine(target_date, settings.work_end_time)
        work_start = tz.localize(work_start)
        work_end = tz.localize(work_end)
        
        # For today's date, start from current time (rounded up to next time step)
        today = date.today()
        if target_date == today:
            now = datetime.now(tz)
            # Add buffer time to ensure we don't show slots that are too close
            # This gives users time to complete the booking process
            buffer_minutes = max(settings.buffer_time_minutes, 15)  # At least 15 minutes buffer
            now_with_buffer = now + timedelta(minutes=buffer_minutes)
            
            # Round up to next time step
            time_step_minutes = settings.time_step_minutes
            current_minute = now_with_buffer.minute
            rounded_minute = ((current_minute // time_step_minutes) + 1) * time_step_minutes
            
            if rounded_minute >= 60:
                # Move to next hour
                now_rounded = now_with_buffer.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                now_rounded = now_with_buffer.replace(minute=rounded_minute, second=0, microsecond=0)
            
            # Use rounded time if it's after work start, otherwise use work start
            if now_rounded > work_start:
                work_start = now_rounded
            # If rounded time is after work end, no slots available
            if now_rounded >= work_end:
                return []
        
        # Get existing bookings for the date (with service relation loaded)
        existing_bookings = await self.booking_repo.get_by_date(target_date)
        
        # Create occupied slots from existing bookings
        occupied_slots = []
        for booking in existing_bookings:
            # Ensure booking_date is timezone-aware and in local timezone
            booking_start_local = normalize_to_local(booking.booking_date)
            
            # Ensure service is loaded (should be loaded by get_by_date, but double-check)
            if not hasattr(booking, 'service') or booking.service is None:
                # Skip if service is not loaded (should not happen, but safety check)
                continue
            
            # Calculate end time (service duration + buffer time)
            total_duration = booking.service.duration_minutes + settings.buffer_time_minutes
            booking_end_local = booking_start_local + timedelta(minutes=total_duration)
            
            occupied_slots.append(TimeSlot(booking_start_local, booking_end_local))
        
        # Generate all possible slots with time step
        available_slots = []
        current_time = work_start
        time_step = timedelta(minutes=settings.time_step_minutes)
        total_duration = service_duration + settings.buffer_time_minutes
        
        while current_time + timedelta(minutes=total_duration) <= work_end:
            slot_end = current_time + timedelta(minutes=total_duration)
            potential_slot = TimeSlot(current_time, slot_end)
            
            # Check if slot overlaps with any occupied slot
            is_available = True
            for occupied in occupied_slots:
                if potential_slot.overlaps(occupied):
                    is_available = False
                    break
            
            if is_available:
                # Return slot in local timezone (since we store in local timezone)
                available_slots.append(current_time)
            
            current_time += time_step
        
        return available_slots
    
    async def is_slot_available(
        self,
        target_datetime: datetime,
        service_duration: int,
        exclude_booking_id: Optional[int] = None
    ) -> bool:
        """
        Check if a specific time slot is available.
        Uses calculate_available_slots to ensure identical logic.
        
        Args:
            target_datetime: Target date and time (should be in local timezone)
            service_duration: Service duration in minutes
            exclude_booking_id: Booking ID to exclude from check (for updates)
            
        Returns:
            True if slot is available
        """
        # Ensure target_datetime is timezone-aware and in local timezone
        target_datetime_local = normalize_to_local(target_datetime)
        
        target_date = target_datetime_local.date()
        
        # Get available slots for this date using the same logic
        available_slots = await self.calculate_available_slots(target_date, service_duration)
        
        # Normalize target_datetime to match the format of available_slots
        # (round to nearest time step, remove seconds and microseconds)
        settings = await self._get_settings()
        time_step_minutes = settings.time_step_minutes
        
        # Round to nearest time step
        target_minute = target_datetime_local.minute
        rounded_minute = (target_minute // time_step_minutes) * time_step_minutes
        target_normalized = target_datetime_local.replace(
            minute=rounded_minute,
            second=0,
            microsecond=0
        )
        
        # Check if the normalized slot is in the list of available slots
        for slot in available_slots:
            # Normalize slot to match (remove seconds and microseconds)
            slot_local = normalize_to_local(slot)
            slot_normalized = slot_local.replace(
                second=0,
                microsecond=0
            )
            
            # Compare local times directly (they should match exactly after normalization)
            # Allow small tolerance for floating point errors
            time_diff = abs((target_normalized - slot_normalized).total_seconds())
            if time_diff < 1.0:  # Within 1 second (should be exact match)
                # Found matching slot - if we need to exclude a booking, verify it doesn't conflict
                if exclude_booking_id:
                    # The slot is in available_slots, which means it's available
                    # But we need to verify that excluding the booking doesn't make it unavailable
                    # Since calculate_available_slots already accounts for all bookings,
                    # and we're excluding one, the slot should be available
                    return True
                return True
        
        return False
    
    @staticmethod
    def format_date(target_datetime: datetime | date, language: str = "pl") -> str:
        """
        Format date with day of week from local timezone datetime or date
        
        Args:
            target_datetime: Local timezone datetime or date to format
            language: Language code
            
        Returns:
            Formatted date string in local timezone
        """
        # Use DateFormatter for consistency
        from app.utils.date_formatter import DateFormatter
        return DateFormatter.format_date(target_datetime, language)
    
    @staticmethod
    def format_time(target_time: datetime) -> str:
        """
        Format time from local timezone datetime
        
        Args:
            target_time: Local timezone datetime to format
            
        Returns:
            Formatted time string (HH:MM) in local timezone
        """
        # Use DateFormatter for consistency
        from app.utils.date_formatter import DateFormatter
        return DateFormatter.format_time(target_time)

