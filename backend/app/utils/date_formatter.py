"""Date and time formatting utilities"""

from datetime import datetime, date
from typing import Union

from app.core.timezone_utils import normalize_to_local


class DateFormatter:
    """
    Static utility class for formatting dates and times.
    
    This class centralizes all date/time formatting logic,
    ensuring consistency across the application.
    
    Uses SOLID principles:
    - Single Responsibility: Only handles date/time formatting
    - Open/Closed: Can be extended without modifying existing code
    """
    
    # Weekday names in Polish
    WEEKDAYS_PL = [
        "Poniedziałek",
        "Wtorek",
        "Środa",
        "Czwartek",
        "Piątek",
        "Sobota",
        "Niedziela"
    ]
    
    # Weekday names in Russian
    WEEKDAYS_RU = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье"
    ]
    
    @staticmethod
    def format_date(target_datetime: Union[datetime, date], language: str = "pl") -> str:
        """
        Format date with day of week from local timezone datetime or date.
        
        Args:
            target_datetime: Local timezone datetime or date to format
            language: Language code ("pl" or "ru")
            
        Returns:
            Formatted date string in format: "Weekday, DD-MM-YYYY"
            
        Example:
            >>> formatted = DateFormatter.format_date(date.today(), "pl")
            >>> # Returns: "Poniedziałek, 19-12-2024"
        """
        # If it's a date object, use it directly
        if isinstance(target_datetime, date):
            target_date = target_datetime
        else:
            # It's a datetime - ensure it's in local timezone
            target_datetime = normalize_to_local(target_datetime)
            target_date = target_datetime.date()
        
        # Select weekday names based on language
        weekdays = DateFormatter.WEEKDAYS_RU if language == "ru" else DateFormatter.WEEKDAYS_PL
        weekday = weekdays[target_date.weekday()]
        
        return f"{weekday}, {target_date.strftime('%d-%m-%Y')}"
    
    @staticmethod
    def format_time(target_time: datetime) -> str:
        """
        Format time from local timezone datetime.
        
        Args:
            target_time: Local timezone datetime to format
            
        Returns:
            Formatted time string in format "HH:MM"
            
        Example:
            >>> formatted = DateFormatter.format_time(datetime.now())
            >>> # Returns: "14:30"
        """
        # Ensure datetime is in local timezone
        target_time = normalize_to_local(target_time)
        return target_time.strftime("%H:%M")
    
    @staticmethod
    def format_datetime(
        target_datetime: datetime,
        language: str = "pl",
        include_time: bool = True
    ) -> str:
        """
        Format both date and time from local timezone datetime.
        
        Args:
            target_datetime: Local timezone datetime to format
            language: Language code ("pl" or "ru")
            include_time: Whether to include time in the output
            
        Returns:
            Formatted datetime string
            
        Example:
            >>> formatted = DateFormatter.format_datetime(datetime.now(), "pl")
            >>> # Returns: "Poniedziałek, 19-12-2024 14:30"
        """
        date_str = DateFormatter.format_date(target_datetime, language)
        
        if include_time:
            time_str = DateFormatter.format_time(target_datetime)
            return f"{date_str} {time_str}"
        
        return date_str

