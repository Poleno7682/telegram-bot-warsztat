"""System settings repository"""

from typing import Optional
from datetime import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import SystemSettings
from .base import BaseRepository


class SettingsRepository(BaseRepository[SystemSettings]):
    """Repository for SystemSettings model (Singleton)"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(SystemSettings, session)
    
    async def get_settings(self, sync_with_env: bool = False) -> SystemSettings:
        """
        Get system settings (singleton)
        
        Args:
            sync_with_env: If True, syncs with .env file values (used on startup)
        
        Returns:
            System settings instance
        """
        result = await self.session.execute(
            select(SystemSettings).where(SystemSettings.id == 1)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Create default settings if not exists
            settings = await self.create_default_settings()
        elif sync_with_env:
            # Sync with .env file values (only when explicitly requested, e.g., on startup)
            await self.sync_with_env(settings)
        
        return settings
    
    async def sync_with_env(self, settings: SystemSettings) -> SystemSettings:
        """
        Sync settings with values from .env file
        
        Args:
            settings: Existing settings instance
            
        Returns:
            Updated settings instance
        """
        # Get default values from .env file
        from app.config.settings import get_settings
        env_settings = get_settings()
        
        # Parse work start/end times from .env (format: "HH:MM")
        def parse_time(time_str: str) -> time:
            """Parse time string in format HH:MM"""
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]))
        
        work_start = parse_time(env_settings.default_work_start)
        work_end = parse_time(env_settings.default_work_end)
        
        # Update settings from .env
        settings.work_start_time = work_start
        settings.work_end_time = work_end
        settings.time_step_minutes = env_settings.default_time_step
        settings.buffer_time_minutes = env_settings.default_buffer_time
        settings.timezone = env_settings.timezone
        # booking_days_ahead doesn't have a .env default, keep existing value
        
        await self.session.flush()
        await self.session.refresh(settings)
        return settings
    
    async def create_default_settings(self) -> SystemSettings:
        """
        Create default system settings using values from .env file
        
        Returns:
            Created settings
        """
        # Get default values from .env file
        from app.config.settings import get_settings
        env_settings = get_settings()
        
        # Parse work start/end times from .env (format: "HH:MM")
        def parse_time(time_str: str) -> time:
            """Parse time string in format HH:MM"""
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]))
        
        work_start = parse_time(env_settings.default_work_start)
        work_end = parse_time(env_settings.default_work_end)
        
        settings = SystemSettings(
            id=1,
            work_start_time=work_start,
            work_end_time=work_end,
            time_step_minutes=env_settings.default_time_step,
            buffer_time_minutes=env_settings.default_buffer_time,
            timezone=env_settings.timezone,
            booking_days_ahead=14  # This doesn't have a .env default, keep hardcoded
        )
        self.session.add(settings)
        await self.session.flush()
        await self.session.refresh(settings)
        return settings
    
    async def update_work_hours(
        self,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None
    ) -> SystemSettings:
        """
        Update work hours
        
        Args:
            start_time: Work start time
            end_time: Work end time
            
        Returns:
            Updated settings
        """
        settings = await self.get_settings()
        
        if start_time:
            settings.work_start_time = start_time
        if end_time:
            settings.work_end_time = end_time
        
        await self.session.flush()
        await self.session.refresh(settings)
        return settings
    
    async def update_time_settings(
        self,
        time_step_minutes: Optional[int] = None,
        buffer_time_minutes: Optional[int] = None
    ) -> SystemSettings:
        """
        Update time step and buffer settings
        
        Args:
            time_step_minutes: Time step in minutes
            buffer_time_minutes: Buffer time in minutes
            
        Returns:
            Updated settings
        """
        settings = await self.get_settings()
        
        if time_step_minutes:
            settings.time_step_minutes = time_step_minutes
        if buffer_time_minutes:
            settings.buffer_time_minutes = buffer_time_minutes
        
        await self.session.flush()
        await self.session.refresh(settings)
        return settings
    
    async def update_booking_days(self, days: int) -> SystemSettings:
        """
        Update booking days ahead
        
        Args:
            days: Number of days to show for booking
            
        Returns:
            Updated settings
        """
        settings = await self.get_settings()
        settings.booking_days_ahead = days
        
        await self.session.flush()
        await self.session.refresh(settings)
        return settings

