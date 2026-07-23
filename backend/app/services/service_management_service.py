"""Service Management Service - Business logic for service management"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.dto import ServiceCreateData, ServiceUpdateData
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
    
    async def create_service(self, data: ServiceCreateData) -> Service:
        """
        Create new service

        Args:
            data: Fields for the new service

        Returns:
            Created service
        """
        service = await self.service_repo.create_service(data)
        await self.session.commit()
        return service

    async def update_service(
        self,
        service_id: int,
        data: ServiceUpdateData
    ) -> Optional[Service]:
        """
        Update service. Fields left as None on `data` are unchanged.

        Args:
            service_id: Service ID
            data: Fields to update

        Returns:
            Updated service or None if not found
        """
        service = await self.service_repo.update_service(service_id, data)
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

