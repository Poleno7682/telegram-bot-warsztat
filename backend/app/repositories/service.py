"""Service repository"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
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
        return await self.create(
            name_pl=name_pl,
            name_ru=name_ru,
            duration_minutes=duration_minutes,
            price=price,
            description_pl=description_pl,
            description_ru=description_ru
        )
    
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
        service = await self.get_by_id(service_id)
        if not service:
            return None
        
        if name_pl is not None:
            service.name_pl = name_pl
        if name_ru is not None:
            service.name_ru = name_ru
        if duration_minutes is not None:
            service.duration_minutes = duration_minutes
        if price is not None:
            service.price = price
        if description_pl is not None:
            service.description_pl = description_pl
        if description_ru is not None:
            service.description_ru = description_ru
        
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

