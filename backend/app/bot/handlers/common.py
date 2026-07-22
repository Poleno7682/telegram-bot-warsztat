"""Common handlers - main menu and navigation"""

from typing import Callable, Union, Tuple

from aiogram import Router, F
from aiogram.types import Message as TelegramMessage, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from app.models.user import User
from app.bot.ui.menu import build_menu_payload as _build_menu_payload, schedule_main_menu_return

router = Router(name="common")

# Re-exported for backward compatibility: handlers across the codebase import
# schedule_main_menu_return from this module. The implementation itself lives
# in app.bot.ui.menu, which app.services.notification_service also depends on
# (services must not import from app.bot.handlers - see
# docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md, item 1.1).
__all__ = [
    "router",
    "safe_callback_answer",
    "send_clean_menu",
    "schedule_main_menu_return",
    "show_main_menu",
    "edit_or_ignore",
]


async def edit_or_ignore(callback: CallbackQuery, text: str, **kwargs) -> bool:
    """
    Edit callback.message's text if it's a real, editable Message.

    callback.message can be an InaccessibleMessage (e.g. too old, or the bot
    was restarted) - in that case there's nothing sensible to edit, so this
    is a no-op. Introduced to replace the repeated
    `if isinstance(callback.message, TelegramMessage): await callback.message.edit_text(...)`
    guard that appeared ~40 times across the booking/mechanic handlers - see
    docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md, item 2.2.

    Args:
        callback: Callback query whose message should be edited
        text: New text
        **kwargs: Extra arguments forwarded to edit_text (e.g. reply_markup)

    Returns:
        True if the message was edited, False if there was nothing to edit
    """
    if not isinstance(callback.message, TelegramMessage):
        return False
    await callback.message.edit_text(text, **kwargs)
    return True


async def safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False
) -> None:
    """
    Safely answer callback query, ignoring errors for old queries
    
    Args:
        callback: Callback query to answer
        text: Optional text to show
        show_alert: Whether to show as alert
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as e:
        # Ignore errors for old queries or invalid query IDs
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Query is too old, silently ignore
            pass
        else:
            # Re-raise other errors
            raise


async def send_clean_menu(
    callback: CallbackQuery,
    text: str,
    reply_markup,
    delete_previous: bool = True
) -> TelegramMessage | None:
    """
    Send menu message with optional deletion of previous message
    
    Args:
        callback: Callback query
        text: Message text
        reply_markup: Keyboard markup
        delete_previous: Whether to delete previous message
        
    Returns:
        Sent message or None if bot is not available
    """
    if not isinstance(callback.message, TelegramMessage) or not callback.bot:
        return None
    
    # Delete previous message if requested
    if delete_previous:
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            # Message already deleted or too old
            pass
    
    # Send new message
    return await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=reply_markup
    )


async def show_main_menu(
    source: Union[TelegramMessage, CallbackQuery],
    user: User,
    delete_previous: bool = True
):
    """
    Show main menu based on user role
    
    Args:
        source: Message or CallbackQuery to respond to
        user: User object
        delete_previous: Whether to delete previous message (only for callbacks)
    """
    menu_text, keyboard = _build_menu_payload(user)
    
    # Handle different source types
    if isinstance(source, CallbackQuery):
        # For callback queries - delete previous and send new
        await send_clean_menu(
            callback=source,
            text=menu_text,
            reply_markup=keyboard,
            delete_previous=delete_previous
        )
    else:
        # For direct messages - just send
        await source.answer(menu_text, reply_markup=keyboard)


@router.message(Command("menu"))
async def cmd_menu(message: TelegramMessage, user: User):
    """
    Handle /menu command
    
    Args:
        message: Message from user
        user: User object (injected by middleware)
    """
    await show_main_menu(message, user)


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery, user: User):
    """
    Handle main menu callback
    
    Args:
        callback: Callback query
        user: User object
    """
    await show_main_menu(callback, user)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, user: User):
    """
    Handle cancel callback
    
    Args:
        callback: Callback query
        user: User object
    """
    # Show main menu (will delete current message and send new)
    await show_main_menu(callback, user)
    await safe_callback_answer(callback)

