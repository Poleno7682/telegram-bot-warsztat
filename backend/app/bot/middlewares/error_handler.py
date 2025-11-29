"""Global error handler middleware for aiogram exceptions"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramUnauthorizedError,
    TelegramNotFound,
    TelegramMigrateToChat,
    TelegramNetworkError,
    TelegramConflictError,
    TelegramRetryAfter,
    TelegramServerError,
)
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware to handle all aiogram exceptions globally"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Wrap handler execution with error handling
        
        Args:
            handler: Handler function
            event: Telegram event
            data: Handler data dictionary
            
        Returns:
            Handler result or None if error occurred
        """
        try:
            return await handler(event, data)
        except TelegramRetryAfter as e:
            # Flood control exceeded - wait and retry
            logger.warning(
                "Flood control exceeded",
                retry_after=e.retry_after,
                method=type(e.method).__name__ if hasattr(e, 'method') else None,
                exc_info=True
            )
            # Note: In production, you might want to implement retry logic here
            await self._send_error_message(event, "errors.rate_limit", data)
            return None
        except TelegramBadRequest as e:
            # Bad request - usually means invalid data or old query
            error_msg = str(e)
            if "query is too old" in error_msg or "query ID is invalid" in error_msg:
                # Old callback query - silently ignore
                logger.debug("Old callback query ignored", error=error_msg)
                return None
            elif "message is not modified" in error_msg:
                # Message not modified - silently ignore
                logger.debug("Message not modified", error=error_msg)
                return None
            elif "message to edit not found" in error_msg:
                # Message to edit not found - silently ignore
                logger.debug("Message to edit not found", error=error_msg)
                return None
            elif "chat not found" in error_msg.lower():
                # Chat not found - user blocked bot or chat deleted
                logger.warning("Chat not found", error=error_msg, exc_info=True)
                return None
            else:
                # Other bad requests - log and notify user
                logger.warning("Bad request", error=error_msg, exc_info=True)
                await self._send_error_message(event, "errors.bad_request", data)
                return None
        except TelegramForbiddenError as e:
            # Bot is forbidden (kicked from chat, blocked by user)
            logger.warning("Bot forbidden", error=str(e), exc_info=True)
            # Don't try to send message - bot is blocked
            return None
        except TelegramUnauthorizedError as e:
            # Invalid bot token
            logger.error("Unauthorized - invalid bot token", error=str(e), exc_info=True)
            # This is a critical error - should stop the bot
            raise
        except TelegramNotFound as e:
            # Entity not found (chat, message, user, etc.)
            logger.warning("Entity not found", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.not_found", data)
            return None
        except TelegramMigrateToChat as e:
            # Chat migrated to supergroup
            logger.info(
                "Chat migrated to supergroup",
                old_chat_id=getattr(e.method, 'chat_id', None),
                new_chat_id=e.migrate_to_chat_id,
                exc_info=True
            )
            # Try to send message to new chat
            if isinstance(event, Message):
                try:
                    chat_id = event.chat.id
                    if chat_id != e.migrate_to_chat_id:
                        # Update chat_id in data if needed
                        pass
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery) and event.message:
                try:
                    chat_id = event.message.chat.id
                    if chat_id != e.migrate_to_chat_id:
                        # Update chat_id in data if needed
                        pass
                except Exception:
                    pass
            await self._send_error_message(event, "errors.chat_migrated", data)
            return None
        except TelegramConflictError as e:
            # Bot token already in use (another instance running)
            logger.error("Bot conflict - token already in use", error=str(e), exc_info=True)
            # This is a critical error - should stop the bot
            raise
        except TelegramNetworkError as e:
            # Network error (connection issues, timeout, etc.)
            logger.error("Network error", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.network_error", data)
            return None
        except TelegramServerError as e:
            # Telegram server error (5xx)
            logger.error("Telegram server error", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.server_error", data)
            return None
        except TelegramAPIError as e:
            # Other Telegram API errors
            logger.error("Telegram API error", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.telegram_error", data)
            return None
        except SQLAlchemyError as e:
            # Database errors
            logger.error("Database error", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.database_error", data)
            return None
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            # Programming errors - log but don't expose to user
            logger.error("Programming error", error=str(e), exc_info=True)
            await self._send_error_message(event, "errors.unknown", data)
            return None
        except Exception as e:
            # Catch-all for any other exceptions
            logger.error("Unexpected error", error=str(e), error_type=type(e).__name__, exc_info=True)
            await self._send_error_message(event, "errors.unknown", data)
            return None
    
    async def _send_error_message(
        self,
        event: TelegramObject,
        error_key: str,
        data: Dict[str, Any] | None = None
    ) -> None:
        """
        Send error message to user
        
        Args:
            event: Telegram event
            error_key: Localization key for error message
            data: Handler data dictionary (optional, for getting user language)
        """
        try:
            from app.core.i18n import get_text
            from app.config.settings import get_settings
            from app.models.user import LANGUAGE_UNSET
            
            # Try to get user language from data (injected by middleware)
            language = None
            if data:
                user = data.get("user")
                if user and hasattr(user, 'language') and user.language and user.language != LANGUAGE_UNSET:
                    language = user.language
                else:
                    # Try to get translation function from data
                    _ = data.get("_")
                    if _:
                        # Use translation function to get error text
                        try:
                            error_text = _(error_key)
                            if isinstance(event, Message):
                                await event.answer(error_text)
                            elif isinstance(event, CallbackQuery):
                                if isinstance(event.message, Message):
                                    await event.message.answer(error_text)
                                await event.answer()
                            return
                        except Exception:
                            pass
            
            # Fallback to default language
            if not language:
                settings = get_settings()
                language = settings.supported_languages_list[0] if settings.supported_languages_list else "pl"
            
            error_text = get_text(error_key, language)
            
            if isinstance(event, Message):
                try:
                    await event.answer(error_text)
                except Exception:
                    logger.debug("Failed to send error message to user", exc_info=True)
            elif isinstance(event, CallbackQuery):
                try:
                    if isinstance(event.message, Message):
                        await event.message.answer(error_text)
                    await event.answer()
                except Exception:
                    logger.debug("Failed to send error message to user", exc_info=True)
        except Exception as e:
            # Don't log error sending errors to avoid infinite loops
            logger.debug("Failed to send error message", error=str(e))

