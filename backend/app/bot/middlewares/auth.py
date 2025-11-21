"""Authentication middleware"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import AuthService
from app.core.i18n import get_text


class AuthMiddleware(BaseMiddleware):
    """Middleware for authentication and authorization"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Check user authorization before processing
        
        Args:
            handler: Handler function
            event: Telegram event
            data: Handler data dictionary
            
        Returns:
            Handler result or None if unauthorized
        """
        # Get user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        # Get database session
        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)
        
        # Check authorization
        auth_service = AuthService(session)
        
        # Skip auth check for /start command
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)
        
        is_authorized = await auth_service.is_authorized(user.id)
        
        if not is_authorized:
            # Send unauthorized message
            message_text = get_text("start.unauthorized_both", "pl")
            
            if isinstance(event, Message):
                await event.answer(message_text)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(message_text)
                await event.answer()
            
            return None
        
        # Get or create user and inject into data
        db_user, _ = await auth_service.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        
        data["user"] = db_user
        
        return await handler(event, data)

