"""Service Management Service - Business logic for service management"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.repositories.service import ServiceRepository


class ServiceManagementService:
    """Service for managing services (SRP - Single Responsibility)"""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize service management service
        
        Args:
            session: Database session
        """
        self.session = session
        self.service_repo = ServiceRepository(session)
    
    async def get_all_active_services(self) -> List[Service]:
        """
        Get all active services
        
        Returns:
            List of active services
        """
        return await self.service_repo.get_all_active()
    
    async def get_service_by_id(self, service_id: int) -> Optional[Service]:
        """
        Get service by ID
        
        Args:
            service_id: Service ID
            
        Returns:
            Service or None if not found
        """
        return await self.service_repo.get_by_id(service_id)
    
    async def create_service(
        self,
        name_pl: str,
        name_ru: str,
        duration_minutes: int,
        price: Optional[float] = None,
        description_pl: Optional[str] = None,
        description_ru: Optional[str] = None
    ) -> Service:
        """
        Create new service
        
        Args:
            name_pl: Service name in Polish
            name_ru: Service name in Russian
            duration_minutes: Service duration in minutes
            price: Service price (optional)
            description_pl: Description in Polish (optional)
            description_ru: Description in Russian (optional)
            
        Returns:
            Created service
        """
        service = await self.service_repo.create(
            name_pl=name_pl,
            name_ru=name_ru,
            duration_minutes=duration_minutes,
            price=price,
            description_pl=description_pl,
            description_ru=description_ru,
            is_active=True
        )
        await self.session.commit()
        return service
    
    async def update_service(
        self,
        service_id: int,
        name_pl: Optional[str] = None,
        name_ru: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        price: Optional[float] = None,
        description_pl: Optional[str] = None,
        description_ru: Optional[str] = None
    ) -> Optional[Service]:
        """
        Update service
        
        Args:
            service_id: Service ID
            name_pl: Service name in Polish
            name_ru: Service name in Russian
            duration_minutes: Service duration in minutes
            price: Service price
            description_pl: Description in Polish
            description_ru: Description in Russian
            
        Returns:
            Updated service or None if not found
        """
        service = await self.service_repo.update_service(
            service_id=service_id,
            name_pl=name_pl,
            name_ru=name_ru,
            duration_minutes=duration_minutes,
            price=price,
            description_pl=description_pl,
            description_ru=description_ru
        )
        if service:
            await self.session.commit()
        return service
    
    async def delete_service(self, service_id: int) -> bool:
        """
        Delete (deactivate) service
        
        Args:
            service_id: Service ID
            
        Returns:
            True if deleted, False if not found
        """
        success = await self.service_repo.deactivate_service(service_id)
        if success:
            await self.session.commit()
        return success

