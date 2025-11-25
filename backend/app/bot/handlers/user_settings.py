"""User settings handlers"""

from typing import Callable
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.repositories.user import UserRepository
from app.bot.keyboards.inline import (
    get_user_settings_keyboard,
    get_language_keyboard,
    get_reminder_settings_keyboard
)
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


def get_language_display_name(language: str | None) -> str:
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


def get_reminder_status_text(user: User, _: Callable[[str], str]) -> str:
    """Build reminder settings text"""
    def fmt(enabled: bool) -> str:
        return _("user_settings.reminders_on") if enabled else _("user_settings.reminders_off")
    
    return _("user_settings.reminders_info").format(
        status_3h=fmt(user.reminder_3h_enabled),
        status_1h=fmt(user.reminder_1h_enabled),
        status_30m=fmt(user.reminder_30m_enabled)
    )


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
    # Use user's language or show "Not set" if None
    if user.language:
        language_name = get_language_display_name(user.language)
    else:
        language_name = _("user_settings.language_not_set")
    
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
        reply_markup=get_user_settings_keyboard(_, user.role == UserRole.MECHANIC)
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
            reply_markup=get_user_settings_keyboard(new_, updated_user.role == UserRole.MECHANIC)
        )
    
    await callback.answer()


@router.callback_query(F.data == "user_settings:reminders")
async def show_reminder_settings(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str]
):
    """Display reminder settings menu for mechanics"""
    if user.role != UserRole.MECHANIC:
        await callback.answer(_("errors.permission_denied"), show_alert=True)
        return
    
    text = get_reminder_status_text(user, _)
    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_reminder_settings_keyboard(
            user.reminder_3h_enabled,
            user.reminder_1h_enabled,
            user.reminder_30m_enabled,
            _
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_settings:toggle_reminder:"))
async def toggle_reminder_setting(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Toggle specific reminder interval"""
    if user.role != UserRole.MECHANIC:
        await callback.answer(_("errors.permission_denied"), show_alert=True)
        return
    
    if not callback.data:
        await callback.answer()
        return
    
    target = callback.data.split(":")[-1]
    valid_fields = {
        "3h": "reminder_3h_enabled",
        "1h": "reminder_1h_enabled",
        "30m": "reminder_30m_enabled"
    }
    attr_name = valid_fields.get(target)
    if not attr_name:
        await callback.answer()
        return
    
    new_value = not getattr(user, attr_name)
    
    repo = UserRepository(session)
    updated_user = await repo.update_reminder_settings(
        user.telegram_id,
        **{attr_name: new_value}
    )
    if updated_user:
        await session.commit()
        setattr(user, attr_name, new_value)
        
        await send_clean_menu(
            callback=callback,
            text=get_reminder_status_text(user, _),
            reply_markup=get_reminder_settings_keyboard(
                user.reminder_3h_enabled,
                user.reminder_1h_enabled,
                user.reminder_30m_enabled,
                _
            )
        )
    
    await callback.answer()

