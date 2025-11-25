"""Internationalization middleware"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.models.user import User
from app.core.i18n import get_i18n_loader


class I18nMiddleware(BaseMiddleware):
    """Middleware for internationalization"""
    
    def __init__(self):
        super().__init__()
        self.i18n = get_i18n_loader()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Inject i18n helper into handler data
        
        Args:
            handler: Handler function
            event: Telegram event
            data: Handler data dictionary
            
        Returns:
            Handler result
        """
        # Get user from data (injected by AuthMiddleware)
        user: User = data.get("user")
        # Use user's language or fallback to first supported language
        if user and user.language:
            language = user.language
        else:
            from app.config.settings import get_settings
            settings = get_settings()
            language = settings.supported_languages_list[0] if settings.supported_languages_list else "pl"
        
        # Create helper function for getting text
        def _(key: str, **kwargs) -> str:
            """Get translated text"""
            return self.i18n.get(key, language, **kwargs)
        
        # Inject into data
        data["_"] = _
        data["language"] = language
        
        return await handler(event, data)

