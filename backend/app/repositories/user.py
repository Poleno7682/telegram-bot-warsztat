"""User repository"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, LANGUAGE_UNSET
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_role(self, role: UserRole) -> List[User]:
        """
        Get all users with specific role
        
        Args:
            role: User role
            
        Returns:
            List of users with the role
        """
        result = await self.session.execute(
            select(User).where(User.role == role, User.is_active == True)
        )
        return list(result.scalars().all())
    
    async def get_all_mechanics(self) -> List[User]:
        """Get all active mechanics"""
        return await self.get_by_role(UserRole.MECHANIC)
    
    async def get_all_admins(self) -> List[User]:
        """Get all active admins"""
        return await self.get_by_role(UserRole.ADMIN)
    
    async def create_or_update_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.USER,
        language: Optional[str] = LANGUAGE_UNSET
    ) -> User:
        """
        Create new user or update existing user
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
            role: User role
            language: Preferred language
            
        Returns:
            User instance
        """
        existing_user = await self.get_by_telegram_id(telegram_id)
        
        if existing_user:
            # Update existing user
            existing_user.username = username
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            await self.session.flush()
            await self.session.refresh(existing_user)
            return existing_user
        else:
            # Create new user
            return await self.create(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role,
                language=language
            )
    
    async def update_language(self, telegram_id: int, language: str) -> Optional[User]:
        """
        Update user's language preference
        
        Args:
            telegram_id: Telegram user ID
            language: New language code
            
        Returns:
            Updated user or None if not found
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.language = language
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def update_reminder_settings(
        self,
        telegram_id: int,
        *,
        reminder_3h_enabled: Optional[bool] = None,
        reminder_1h_enabled: Optional[bool] = None,
        reminder_30m_enabled: Optional[bool] = None
    ) -> Optional[User]:
        """
        Update user's reminder preferences
        """
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        if reminder_3h_enabled is not None:
            user.reminder_3h_enabled = reminder_3h_enabled
        if reminder_1h_enabled is not None:
            user.reminder_1h_enabled = reminder_1h_enabled
        if reminder_30m_enabled is not None:
            user.reminder_30m_enabled = reminder_30m_enabled
        
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def update_role(self, telegram_id: int, role: UserRole) -> Optional[User]:
        """
        Update user's role
        
        Args:
            telegram_id: Telegram user ID
            role: New role
            
        Returns:
            Updated user or None if not found
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.role = role
            await self.session.flush()
            await self.session.refresh(user)
        return user
    
    async def deactivate_user(self, telegram_id: int) -> bool:
        """
        Deactivate user
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if deactivated, False if not found
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.is_active = False
            await self.session.flush()
            return True
        return False

