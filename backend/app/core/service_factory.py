"""Service Factory - Simple factory for creating service instances"""

from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.services.auth_service import AuthService
    from app.services.booking_service import BookingService
    from app.services.service_management_service import ServiceManagementService
    from app.services.settings_management_service import SettingsManagementService
    from app.services.time_service import TimeService
    from app.services.notification_service import NotificationService
    from aiogram import Bot


class ServiceFactory:
    """Simple factory for creating service instances (Dependency Injection helper)"""
    
    def __init__(self, session: AsyncSession, bot: "Bot | None" = None):
        """
        Initialize service factory
        
        Args:
            session: Database session
            bot: Bot instance (optional, for notification services)
        """
        self.session = session
        self.bot = bot
    
    def get_auth_service(self) -> "AuthService":
        """Get AuthService instance"""
        from app.services.auth_service import AuthService
        return AuthService(self.session)
    
    def get_booking_service(self) -> "BookingService":
        """Get BookingService instance"""
        from app.services.booking_service import BookingService
        return BookingService(self.session)
    
    def get_service_management_service(self) -> "ServiceManagementService":
        """Get ServiceManagementService instance"""
        from app.services.service_management_service import ServiceManagementService
        return ServiceManagementService(self.session)
    
    def get_settings_management_service(self) -> "SettingsManagementService":
        """Get SettingsManagementService instance"""
        from app.services.settings_management_service import SettingsManagementService
        return SettingsManagementService(self.session)
    
    def get_time_service(self) -> "TimeService":
        """Get TimeService instance"""
        from app.services.time_service import TimeService
        return TimeService(self.session)
    
    def get_notification_service(self) -> "NotificationService":
        """Get NotificationService instance (requires bot)"""
        if not self.bot:
            raise ValueError("Bot instance required for NotificationService")
        from app.services.notification_service import NotificationService
        return NotificationService(self.session, self.bot)

