"""Authentication and Authorization Service"""

from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.config.settings import get_settings


class AuthService:
    """Service for handling authentication and authorization (SRP - Single Responsibility)"""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize auth service
        
        Args:
            session: Database session
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.settings = get_settings()
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language: str = "pl"
    ) -> Tuple[User, bool]:
        """
        Get existing user or create new one
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: First name
            last_name: Last name
            language: Preferred language
            
        Returns:
            Tuple of (User, is_new)
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        
        if user:
            # Update user info
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await self.session.commit()
            return user, False
        
        # Check if user should be auto-assigned a role from env
        role = await self._determine_initial_role(telegram_id)
        
        # Create new user
        user = await self.user_repo.create_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=role,
            language=language
        )
        await self.session.commit()
        
        return user, True
    
    async def _determine_initial_role(self, telegram_id: int) -> UserRole:
        """
        Determine initial role based on env configuration
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User role
        """
        # Check if admin
        if telegram_id in self.settings.admin_ids_list:
            return UserRole.ADMIN
        
        # Check if mechanic
        if telegram_id in self.settings.mechanic_ids_list:
            return UserRole.MECHANIC
        
        # Check if regular user
        if telegram_id in self.settings.user_ids_list:
            return UserRole.USER
        
        # Default: no role (unauthorized)
        return UserRole.USER
    
    async def is_authorized(self, telegram_id: int) -> bool:
        """
        Check if user is authorized to use the bot
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if authorized
        """
        # Check environment lists
        if (telegram_id in self.settings.admin_ids_list or
            telegram_id in self.settings.mechanic_ids_list or
            telegram_id in self.settings.user_ids_list):
            return True
        
        # Check database
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        return user is not None and user.is_active
    
    async def has_permission(self, telegram_id: int, required_role: UserRole) -> bool:
        """
        Check if user has required permission level
        
        Args:
            telegram_id: Telegram user ID
            required_role: Required role
            
        Returns:
            True if user has permission
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user or not user.is_active:
            return False
        
        # Admin has all permissions
        if user.role == UserRole.ADMIN:
            return True
        
        # Mechanic has USER permissions
        if user.role == UserRole.MECHANIC and required_role == UserRole.USER:
            return True
        
        return user.role == required_role
    
    async def update_user_language(self, telegram_id: int, language: str) -> Optional[User]:
        """
        Update user's language preference
        
        Args:
            telegram_id: Telegram user ID
            language: New language code
            
        Returns:
            Updated user or None
        """
        user = await self.user_repo.update_language(telegram_id, language)
        if user:
            await self.session.commit()
        return user
    
    async def assign_role(
        self,
        admin_telegram_id: int,
        target_telegram_id: int,
        role: UserRole
    ) -> Tuple[bool, str]:
        """
        Assign role to user (admin only)
        
        Args:
            admin_telegram_id: Admin's Telegram ID
            target_telegram_id: Target user's Telegram ID
            role: Role to assign
            
        Returns:
            Tuple of (success, message)
        """
        # Check if requester is admin
        if not await self.has_permission(admin_telegram_id, UserRole.ADMIN):
            return False, "Permission denied"
        
        # Get or create target user
        target_user = await self.user_repo.get_by_telegram_id(target_telegram_id)
        
        if not target_user:
            # Create new user with role
            target_user = await self.user_repo.create(
                telegram_id=target_telegram_id,
                role=role,
                is_active=True
            )
        else:
            # Update existing user's role
            target_user.role = role
            target_user.is_active = True
        
        await self.session.commit()
        return True, f"Role {role.value} assigned successfully"
    
    async def remove_user(
        self,
        admin_telegram_id: int,
        target_telegram_id: int
    ) -> Tuple[bool, str]:
        """
        Remove user (deactivate) - admin only
        
        Args:
            admin_telegram_id: Admin's Telegram ID
            target_telegram_id: Target user's Telegram ID
            
        Returns:
            Tuple of (success, message)
        """
        # Check if requester is admin
        if not await self.has_permission(admin_telegram_id, UserRole.ADMIN):
            return False, "Permission denied"
        
        # Deactivate user
        success = await self.user_repo.deactivate_user(target_telegram_id)
        await self.session.commit()
        
        if success:
            return True, "User removed successfully"
        return False, "User not found"
    
    async def add_user_role(self, telegram_id: int, role: UserRole) -> Optional[User]:
        """
        Add user with specified role or update existing user's role
        
        Args:
            telegram_id: Telegram user ID
            role: Role to assign
            
        Returns:
            User object or None if failed
        """
        # Get or create user
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        
        if user:
            # Update existing user's role
            user.role = role
            user.is_active = True
        else:
            # Create new user with role
            user = await self.user_repo.create(
                telegram_id=telegram_id,
                role=role,
                is_active=True
            )
        
        await self.session.commit()
        return user
    
    async def remove_user_role(self, telegram_id: int) -> bool:
        """
        Remove user by deactivating their account
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if successful, False otherwise
        """
        success = await self.user_repo.deactivate_user(telegram_id)
        if success:
            await self.session.commit()
        return success

