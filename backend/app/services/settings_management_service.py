"""Settings Management Service - Business logic for system settings management"""

from typing import Optional
from datetime import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import SystemSettings
from app.repositories.settings import SettingsRepository


class SettingsManagementService:
    """Service for managing system settings (SRP - Single Responsibility)"""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize settings management service
        
        Args:
            session: Database session
        """
        self.session = session
        self.settings_repo = SettingsRepository(session)
    
    async def get_settings(self) -> SystemSettings:
        """
        Get system settings (singleton)
        
        Returns:
            System settings instance
        """
        return await self.settings_repo.get_settings()
    
    async def update_work_hours(
        self,
        start_time: time,
        end_time: time
    ) -> SystemSettings:
        """
        Update work hours
        
        Args:
            start_time: Work start time
            end_time: Work end time
            
        Returns:
            Updated settings
        """
        settings = await self.settings_repo.update_work_hours(
            start_time=start_time,
            end_time=end_time
        )
        await self.session.commit()
        
        # Update .env file with new values
        from app.utils.env_updater import update_env_file
        update_env_file(
            default_work_start=start_time.strftime("%H:%M"),
            default_work_end=end_time.strftime("%H:%M")
        )
        
        return settings
    
    async def update_time_step(self, time_step_minutes: int) -> SystemSettings:
        """
        Update time step
        
        Args:
            time_step_minutes: Time step in minutes
            
        Returns:
            Updated settings
        """
        settings = await self.settings_repo.update_time_settings(
            time_step_minutes=time_step_minutes
        )
        await self.session.commit()
        
        # Update .env file with new value
        from app.utils.env_updater import update_env_file
        update_env_file(default_time_step=time_step_minutes)
        
        return settings
    
    async def update_buffer_time(self, buffer_time_minutes: int) -> SystemSettings:
        """
        Update buffer time
        
        Args:
            buffer_time_minutes: Buffer time in minutes
            
        Returns:
            Updated settings
        """
        settings = await self.settings_repo.update_time_settings(
            buffer_time_minutes=buffer_time_minutes
        )
        await self.session.commit()
        
        # Update .env file with new value
        from app.utils.env_updater import update_env_file
        update_env_file(default_buffer_time=buffer_time_minutes)
        
        return settings

