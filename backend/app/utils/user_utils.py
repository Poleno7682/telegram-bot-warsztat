"""User utilities - Helper functions for user-related operations"""

from typing import Optional, Tuple
from functools import lru_cache

from app.models.user import User, LANGUAGE_UNSET
from app.repositories.user import UserRepository


@lru_cache(maxsize=1)
def _get_default_language() -> str:
    """Get default language from settings (cached)"""
    from app.config.settings import get_settings
    settings = get_settings()
    return settings.supported_languages_list[0] if settings.supported_languages_list else "pl"


def get_user_language(user: User, fallback: Optional[str] = None) -> str:
    """
    Get user's language preference with fallback support.
    
    This function centralizes the logic for determining user language,
    eliminating code duplication across the codebase.
    
    Args:
        user: User instance
        fallback: Optional fallback language code. If None, uses default from settings
        
    Returns:
        Language code string (e.g., "pl", "ru")
        
    Example:
        >>> language = get_user_language(user)
        >>> language = get_user_language(user, fallback="en")
    """
    # Check if user has a valid language preference
    if user.language and user.language != LANGUAGE_UNSET:
        return user.language
    
    # Use provided fallback if available
    if fallback:
        return fallback
    
    # Use default language from settings
    return _get_default_language()


async def get_user_or_error(
    user_repo: UserRepository,
    telegram_id: int,
    error_message: str = "User not found"
) -> Tuple[Optional[User], Optional[str]]:
    """
    Get user by telegram_id or return error message.
    
    This utility eliminates repetitive user retrieval and error checking
    pattern across services and handlers.
    
    Args:
        user_repo: UserRepository instance
        telegram_id: Telegram user ID
        error_message: Custom error message (optional)
        
    Returns:
        Tuple of (User instance or None, error message or None)
        
    Example:
        >>> user, error = await get_user_or_error(user_repo, telegram_id)
        >>> if error:
        >>>     return None, error
    """
    user = await user_repo.get_by_telegram_id(telegram_id)
    
    if not user:
        return None, error_message
    
    return user, None

