"""Database session middleware"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from app.config.database import AsyncSessionLocal
from app.core.service_factory import ServiceFactory


class DbSessionMiddleware(BaseMiddleware):
    """Middleware to inject database session into handlers"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Create database session and inject it into handler data
        
        Args:
            handler: Handler function
            event: Telegram event
            data: Handler data dictionary
            
        Returns:
            Handler result
        """
        async with AsyncSessionLocal() as session:
            data["session"] = session
            
            # Inject ServiceFactory if bot is available
            bot: Bot | None = data.get("bot")
            if bot:
                data["service_factory"] = ServiceFactory(session, bot)
            else:
                data["service_factory"] = ServiceFactory(session)
            
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

