"""User settings handlers"""

from typing import Callable
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.bot.keyboards.inline import get_user_settings_keyboard, get_language_keyboard
from app.bot.handlers.common import send_clean_menu

router = Router(name="user_settings")


def get_role_display_name(role: UserRole, _: Callable[[str], str]) -> str:
    """
    Get localized role display name
    
    Args:
        role: User role
        _: Translation function
        
    Returns:
        Localized role name
    """
    role_map = {
        UserRole.USER: "user_settings.role_user",
        UserRole.MECHANIC: "user_settings.role_mechanic",
        UserRole.ADMIN: "user_settings.role_admin"
    }
    return _(role_map.get(role, "user_settings.role_user"))


def get_language_display_name(language: str) -> str:
    """
    Get language display name
    
    Args:
        language: Language code
        
    Returns:
        Language name
    """
    language_map = {
        "pl": "Polski 🇵🇱",
        "ru": "Русский 🇷🇺"
    }
    return language_map.get(language, language)


@router.callback_query(F.data == "menu:user_settings")
async def show_user_settings(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str]
):
    """Show user settings menu"""
    # Build full name from first_name and last_name
    name_parts = []
    if user.first_name:
        name_parts.append(user.first_name)
    if user.last_name:
        name_parts.append(user.last_name)
    
    # Get display name: full name → username → ID
    username = " ".join(name_parts) if name_parts else (user.username or f"User{user.telegram_id}")
    
    # Get role display name
    role_name = get_role_display_name(user.role, _)
    
    # Get language display name
    language_name = get_language_display_name(user.language)
    
    # Format info text
    text = _("user_settings.info").format(
        username=username,
        user_id=user.telegram_id,
        role=role_name,
        language=language_name
    )
    
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_user_settings_keyboard(_)
    )
    await callback.answer()


@router.callback_query(F.data == "user_settings:change_language")
async def change_language_start(
    callback: CallbackQuery,
    _: Callable[[str], str]
):
    """Start language change process"""
    await send_clean_menu(
        callback=callback,
        text=_("start.select_language"),
        reply_markup=get_language_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def change_language_process(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Process language change"""
    if not callback.data or not callback.from_user:
        await callback.answer()
        return
    
    language = callback.data.split(":")[1]
    
    # Update user's language
    auth_service = AuthService(session)
    updated_user = await auth_service.update_user_language(
        callback.from_user.id,
        language
    )
    
    if updated_user:
        # Get updated translation function
        from app.core.i18n import get_text
        
        def new_(_key: str, **kwargs) -> str:
            return get_text(_key, language, **kwargs)
        
        # Get language name
        language_name = get_language_display_name(language)
        
        # Show confirmation and return to user settings
        # Build full name from first_name and last_name
        name_parts = []
        if updated_user.first_name:
            name_parts.append(updated_user.first_name)
        if updated_user.last_name:
            name_parts.append(updated_user.last_name)
        
        username = " ".join(name_parts) if name_parts else (updated_user.username or f"User{updated_user.telegram_id}")
        role_name = get_role_display_name(updated_user.role, new_)
        
        text = new_("user_settings.info").format(
            username=username,
            user_id=updated_user.telegram_id,
            role=role_name,
            language=language_name
        )
        
        await send_clean_menu(
            callback=callback,
            text=text,
            reply_markup=get_user_settings_keyboard(new_)
        )
    
    await callback.answer()

