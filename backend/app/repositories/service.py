"""Service repository"""

from dataclasses import asdict
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.dto import ServiceCreateData, ServiceUpdateData
from .base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    """Repository for Service model"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Service, session)
    
    async def get_all_active(self) -> List[Service]:
        """
        Get all active services
        
        Returns:
            List of active services
        """
        result = await self.session.execute(
            select(Service).where(Service.is_active == True).order_by(Service.name_pl)
        )
        return list(result.scalars().all())
    
    async def get_by_name(self, name: str, language: str = "pl") -> Optional[Service]:
        """
        Get service by name
        
        Args:
            name: Service name
            language: Language of the name
            
        Returns:
            Service or None if not found
        """
        if language == "ru":
            condition = Service.name_ru == name
        else:
            condition = Service.name_pl == name
        
        result = await self.session.execute(
            select(Service).where(condition)
        )
        return result.scalar_one_or_none()
    
    async def create_service(self, data: ServiceCreateData) -> Service:
        """
        Create new service

        Args:
            data: Fields for the new service

        Returns:
            Created service
        """
        return await self.create(**asdict(data))

    async def update_service(
        self,
        service_id: int,
        data: ServiceUpdateData
    ) -> Optional[Service]:
        """
        Update service. Fields left as None on `data` are unchanged
        (partial update).

        Args:
            service_id: Service ID
            data: Fields to update

        Returns:
            Updated service or None if not found
        """
        service = await self.get_by_id(service_id)
        if not service:
            return None

        for field, value in asdict(data).items():
            if value is not None:
                setattr(service, field, value)

        await self.session.flush()
        await self.session.refresh(service)
        return service
    
    async def deactivate_service(self, service_id: int) -> bool:
        """
        Deactivate service
        
        Args:
            service_id: Service ID
            
        Returns:
            True if deactivated, False if not found
        """
        service = await self.get_by_id(service_id)
        if service:
            service.is_active = False
            await self.session.flush()
            return True
        return False
    
    async def activate_service(self, service_id: int) -> bool:
        """
        Activate service
        
        Args:
            service_id: Service ID
            
        Returns:
            True if activated, False if not found
        """
        service = await self.get_by_id(service_id)
        if service:
            service.is_active = True
            await self.session.flush()
            return True
        return False

