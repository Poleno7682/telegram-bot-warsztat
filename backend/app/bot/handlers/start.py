"""Start handler - language selection and initial setup"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message as TelegramMessage, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, LANGUAGE_UNSET
from app.services.auth_service import AuthService
from app.bot.keyboards.inline import get_language_keyboard
from app.core.i18n import get_text

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: TelegramMessage,
    session: AsyncSession
):
    """
    Handle /start command
    
    Args:
        message: Message from user
        session: Database session
    """
    if not message.from_user:
        return
    
    auth_service = AuthService(session)
    
    # Check if user is authorized
    is_authorized = await auth_service.is_authorized(message.from_user.id)
    
    if not is_authorized:
        # Send unauthorized message in both languages
        text = get_text("start.unauthorized_both", "pl")
        await message.answer(text)
        return
    
    # Get or create user
    user, is_new = await auth_service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # If new user or language is unset, show language selection
    if is_new or user.language == LANGUAGE_UNSET:
        # Use first supported language as fallback for welcome message
        from app.config.settings import get_settings
        settings = get_settings()
        fallback_lang = settings.supported_languages_list[0] if settings.supported_languages_list else "pl"
        welcome_text = get_text("start.welcome", fallback_lang)
        await message.answer(
            welcome_text,
            reply_markup=get_language_keyboard()
        )
    else:
        # Show main menu
        from app.bot.handlers.common import show_main_menu
        await show_main_menu(message, user)


@router.callback_query(F.data.startswith("lang:"))
async def select_language(
    callback: CallbackQuery,
    session: AsyncSession
):
    """
    Handle language selection
    
    Args:
        callback: Callback query
        session: Database session
    """
    if not callback.data or not callback.from_user:
        await callback.answer()
        return
    
    language = callback.data.split(":")[1]
    
    # Update user's language
    auth_service = AuthService(session)
    user = await auth_service.update_user_language(
        callback.from_user.id,
        language
    )
    
    if user:
        # Show main menu (will delete language selection message)
        from app.bot.handlers.common import show_main_menu
        await show_main_menu(callback, user)
    
    await callback.answer()

