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
    
    async def get_settings(self) -> SystemSettings:
        """
        Get system settings (singleton)
        
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
        
        return settings
    
    async def create_default_settings(self) -> SystemSettings:
        """
        Create default system settings
        
        Returns:
            Created settings
        """
        settings = SystemSettings(
            id=1,
            work_start_time=time(8, 0),
            work_end_time=time(16, 0),
            time_step_minutes=10,
            buffer_time_minutes=15,
            timezone="Europe/Warsaw",
            booking_days_ahead=14
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

