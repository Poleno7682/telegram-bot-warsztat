"""User settings handlers"""

from typing import Callable
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message as TelegramMessage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole, LANGUAGE_UNSET
from app.services.auth_service import AuthService
from app.bot.keyboards.inline import (
    get_user_settings_keyboard,
    get_language_keyboard,
    get_reminder_settings_keyboard
)
from app.bot.handlers.common import safe_callback_answer, send_clean_menu, edit_or_ignore
from app.bot.ui.chat_cleaner import clear_chat_history

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


def get_language_display_name(language: str | None, translate: Callable[[str], str]) -> str:
    """
    Get language display name

    Args:
        language: Language code (can be None or LANGUAGE_UNSET)
        translate: Translation function (i18n getter)

    Returns:
        Language name (shown in its own language - not translated, same as
        any language picker), or the localized "not set" label via the
        same "user_settings.language_not_set" i18n key already used at
        this function's LANGUAGE_UNSET call site.
    """
    if not language or language == LANGUAGE_UNSET:
        return translate("user_settings.language_not_set")
    language_map = {
        "pl": "Polski 🇵🇱",
        "ru": "Русский 🇷🇺"
    }
    return language_map.get(language, language)


def build_user_settings_text(user: User, _: Callable[[str], str]) -> str:
    """Build the "⚙️ Настройки" info text (name, role, language).

    Shared by show_user_settings, change_language_process, and
    clear_chat_confirmed so all three render identical info instead of
    drifting apart via copy-pasted formatting.
    """
    name_parts = []
    if user.first_name:
        name_parts.append(user.first_name)
    if user.last_name:
        name_parts.append(user.last_name)

    # Get display name: full name → username → ID
    username = " ".join(name_parts) if name_parts else (user.username or f"User{user.telegram_id}")

    role_name = get_role_display_name(user.role, _)

    # Use user's language or show "Not set" if unset
    if user.language and user.language != LANGUAGE_UNSET:
        language_name = get_language_display_name(user.language, _)
    else:
        language_name = _("user_settings.language_not_set")

    return _("user_settings.info").format(
        username=username,
        user_id=user.telegram_id,
        role=role_name,
        language=language_name
    )


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
    text = build_user_settings_text(user, _)

    await send_clean_menu(
        callback=callback,
        text=text,
        reply_markup=get_user_settings_keyboard(_, user.role == UserRole.MECHANIC)
    )
    await safe_callback_answer(callback)


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
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("lang:"))
async def change_language_process(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Process language change"""
    if not callback.data or not callback.from_user:
        await safe_callback_answer(callback)
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

        text = build_user_settings_text(updated_user, new_)

        await send_clean_menu(
            callback=callback,
            text=text,
            reply_markup=get_user_settings_keyboard(new_, updated_user.role == UserRole.MECHANIC)
        )
    
    await safe_callback_answer(callback)


@router.callback_query(F.data == "user_settings:reminders")
async def show_reminder_settings(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str]
):
    """Display reminder settings menu for mechanics"""
    if user.role != UserRole.MECHANIC:
        await safe_callback_answer(callback, _("errors.permission_denied"), show_alert=True)
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
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("user_settings:toggle_reminder:"))
async def toggle_reminder_setting(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    _: Callable[[str], str]
):
    """Toggle specific reminder interval"""
    if user.role != UserRole.MECHANIC:
        await safe_callback_answer(callback, _("errors.permission_denied"), show_alert=True)
        return
    
    if not callback.data:
        await safe_callback_answer(callback)
        return
    
    target = callback.data.split(":")[-1]
    valid_fields = {
        "3h": "reminder_3h_enabled",
        "1h": "reminder_1h_enabled",
        "30m": "reminder_30m_enabled"
    }
    attr_name = valid_fields.get(target)
    if not attr_name:
        await safe_callback_answer(callback)
        return
    
    new_value = not getattr(user, attr_name)

    auth_service = AuthService(session)
    updated_user = await auth_service.update_reminder_settings(
        user.telegram_id,
        **{attr_name: new_value}
    )
    if updated_user:
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

    await safe_callback_answer(callback)


@router.callback_query(F.data == "user_settings:clear_chat_ask")
async def clear_chat_ask(callback: CallbackQuery, _: Callable[[str], str]):
    """Ask for confirmation before wiping the chat history - deleting
    dozens/hundreds of messages is irreversible, so this mirrors the
    Yes/No confirmation pattern used for booking cancellation."""
    if not isinstance(callback.message, TelegramMessage):
        await safe_callback_answer(callback)
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=_("common.yes"), callback_data="user_settings:clear_chat_do"),
        InlineKeyboardButton(text=_("common.no"), callback_data="menu:user_settings"),
    )
    await edit_or_ignore(
        callback,
        _("user_settings.clear_chat_confirm"),
        reply_markup=keyboard.as_markup()
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "user_settings:clear_chat_do")
async def clear_chat_confirmed(
    callback: CallbackQuery,
    user: User,
    _: Callable[[str], str]
):
    """Delete every other message in the chat, leaving just this one
    (rewritten into the settings screen) behind - the Bot API has no bulk
    "clear chat" endpoint, see chat_cleaner.clear_chat_history for how
    this actually walks message_id backwards to do it."""
    if not isinstance(callback.message, TelegramMessage) or not callback.bot:
        await safe_callback_answer(callback)
        return

    await clear_chat_history(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
    )

    text = _("user_settings.clear_chat_done") + "\n\n" + build_user_settings_text(user, _)
    await edit_or_ignore(
        callback,
        text,
        reply_markup=get_user_settings_keyboard(_, user.role == UserRole.MECHANIC)
    )
    await safe_callback_answer(callback)

