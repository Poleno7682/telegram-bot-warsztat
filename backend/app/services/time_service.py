"""Time Service for calculating available booking slots"""

from datetime import datetime, date, time, timedelta
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from app.repositories.booking import BookingRepository
from app.repositories.settings import SettingsRepository
from app.models.booking import Booking


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
    
    async def get_available_dates(self, days_ahead: int = None) -> List[date]:
        """
        Get list of available dates for booking
        
        Args:
            days_ahead: Number of days to look ahead (from settings if None)
            
        Returns:
            List of dates
        """
        settings = await self.settings_repo.get_settings()
        
        if days_ahead is None:
            days_ahead = settings.booking_days_ahead
        
        today = date.today()
        dates = []
        
        for i in range(days_ahead):
            target_date = today + timedelta(days=i)
            dates.append(target_date)
        
        return dates
    
    async def get_work_hours(self) -> Tuple[time, time]:
        """
        Get work start and end times
        
        Returns:
            Tuple of (start_time, end_time)
        """
        settings = await self.settings_repo.get_settings()
        return settings.work_start_time, settings.work_end_time
    
    async def get_time_step(self) -> int:
        """
        Get time step in minutes
        
        Returns:
            Time step in minutes
        """
        settings = await self.settings_repo.get_settings()
        return settings.time_step_minutes
    
    async def get_buffer_time(self) -> int:
        """
        Get buffer time in minutes
        
        Returns:
            Buffer time in minutes
        """
        settings = await self.settings_repo.get_settings()
        return settings.buffer_time_minutes
    
    async def calculate_available_slots(
        self,
        target_date: date,
        service_duration: int
    ) -> List[datetime]:
        """
        Calculate all available time slots for a given date and service
        
        Args:
            target_date: Target date
            service_duration: Service duration in minutes
            
        Returns:
            List of available datetime slots
        """
        settings = await self.settings_repo.get_settings()
        
        # Get timezone
        tz = pytz.timezone(settings.timezone)
        
        # Get work hours
        work_start = datetime.combine(target_date, settings.work_start_time)
        work_end = datetime.combine(target_date, settings.work_end_time)
        work_start = tz.localize(work_start)
        work_end = tz.localize(work_end)
        
        # Get existing bookings for the date
        existing_bookings = await self.booking_repo.get_by_date(target_date)
        
        # Create occupied slots from existing bookings
        occupied_slots = []
        for booking in existing_bookings:
            # Ensure booking_date is timezone-aware
            booking_start = booking.booking_date
            if booking_start.tzinfo is None:
                booking_start = tz.localize(booking_start)
            
            # Calculate end time (service duration + buffer)
            total_duration = booking.service.duration_minutes + settings.buffer_time_minutes
            booking_end = booking_start + timedelta(minutes=total_duration)
            
            occupied_slots.append(TimeSlot(booking_start, booking_end))
        
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
                available_slots.append(current_time)
            
            current_time += time_step
        
        return available_slots
    
    async def is_slot_available(
        self,
        target_datetime: datetime,
        service_duration: int,
        exclude_booking_id: int = None
    ) -> bool:
        """
        Check if a specific time slot is available
        
        Args:
            target_datetime: Target date and time
            service_duration: Service duration in minutes
            exclude_booking_id: Booking ID to exclude from check (for updates)
            
        Returns:
            True if slot is available
        """
        settings = await self.settings_repo.get_settings()
        tz = pytz.timezone(settings.timezone)
        
        # Ensure target_datetime is timezone-aware
        if target_datetime.tzinfo is None:
            target_datetime = tz.localize(target_datetime)
        
        # Create slot for the target
        total_duration = service_duration + settings.buffer_time_minutes
        target_slot = TimeSlot(
            target_datetime,
            target_datetime + timedelta(minutes=total_duration)
        )
        
        # Get existing bookings for the date
        existing_bookings = await self.booking_repo.get_by_date(target_datetime.date())
        
        # Check for overlaps
        for booking in existing_bookings:
            # Skip if this is the booking being updated
            if exclude_booking_id and booking.id == exclude_booking_id:
                continue
            
            booking_start = booking.booking_date
            if booking_start.tzinfo is None:
                booking_start = tz.localize(booking_start)
            
            booking_duration = booking.service.duration_minutes + settings.buffer_time_minutes
            booking_end = booking_start + timedelta(minutes=booking_duration)
            
            occupied_slot = TimeSlot(booking_start, booking_end)
            
            if target_slot.overlaps(occupied_slot):
                return False
        
        return True
    
    @staticmethod
    def format_date(target_date: date, language: str = "pl") -> str:
        """
        Format date with day of week
        
        Args:
            target_date: Date to format
            language: Language code
            
        Returns:
            Formatted date string
        """
        weekdays_pl = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
        weekdays_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        
        weekday_names = weekdays_ru if language == "ru" else weekdays_pl
        weekday = weekday_names[target_date.weekday()]
        
        return f"{weekday}, {target_date.strftime('%d-%m-%Y')}"
    
    @staticmethod
    def format_time(target_time: datetime) -> str:
        """
        Format time
        
        Args:
            target_time: Time to format
            
        Returns:
            Formatted time string (HH:MM)
        """
        return target_time.strftime("%H:%M")

