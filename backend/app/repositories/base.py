"""Base repository with common CRUD operations"""

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations following Repository pattern"""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository
        
        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    def _apply_filters(self, query: Select, filters: dict[str, Any]) -> Select:
        """
        Apply equality filters (from get_all/count keyword args) to a query

        Args:
            query: SQLAlchemy select() statement to filter
            filters: Mapping of model attribute name -> value

        Returns:
            Query with WHERE clauses applied for known model attributes
        """
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        return query

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get entity by ID
        
        Args:
            id: Entity ID
            
        Returns:
            Entity or None if not found
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """
        Get all entities with pagination
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filters as keyword arguments
            
        Returns:
            List of entities
        """
        query = self._apply_filters(select(self.model), filters)
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, **data: Any) -> ModelType:
        """
        Create new entity
        
        Args:
            **data: Entity data as keyword arguments
            
        Returns:
            Created entity
        """
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def update(self, id: int, **data: Any) -> Optional[ModelType]:
        """
        Update entity by ID
        
        Args:
            id: Entity ID
            **data: Updated data as keyword arguments
            
        Returns:
            Updated entity or None if not found
        """
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()
    
    async def delete(self, id: int) -> bool:
        """
        Delete entity by ID
        
        Args:
            id: Entity ID
            
        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
    
    async def count(self, **filters) -> int:
        """
        Count entities with optional filters

        Args:
            **filters: Filters as keyword arguments

        Returns:
            Number of entities
        """
        query = self._apply_filters(
            select(func.count()).select_from(self.model), filters
        )
        result = await self.session.execute(query)
        return result.scalar_one()

