"""Main application entry point"""

import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.settings import get_settings
from app.config.database import init_db, close_db
from app.core.logging_config import configure_logging, get_logger
from app.bot.handlers import (
    start,
    common,
    booking,
    mechanic,
    admin,
    user_settings,
    calendar,
    health
)
from app.bot.middlewares import (
    DbSessionMiddleware,
    AuthMiddleware,
    I18nMiddleware,
    ErrorHandlerMiddleware
)
from app.services.reminder_scheduler import ReminderScheduler

# Configure logging (will be configured in main() based on settings)
logger = get_logger(__name__)


reminder_scheduler: ReminderScheduler | None = None


async def on_startup(bot: Bot):
    """Actions to perform on startup"""
    logger.info("Starting bot")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e), exc_info=True)
        raise
    
    # Sync system settings with .env file values on startup
    try:
        from app.config.database import AsyncSessionLocal
        from app.repositories.settings import SettingsRepository
        
        async with AsyncSessionLocal() as session:
            settings_repo = SettingsRepository(session)
            await settings_repo.get_settings(sync_with_env=True)
            await session.commit()
            logger.info("System settings synced with .env file")
    except Exception as e:
        logger.warning("Failed to sync settings with .env", error=str(e), exc_info=True)
        # Don't fail startup if settings sync fails
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info("Bot started", username=bot_info.username, bot_id=bot_info.id)


async def on_shutdown(bot: Bot):
    """Actions to perform on shutdown"""
    logger.info("Shutting down bot")
    
    global reminder_scheduler
    if reminder_scheduler:
        try:
            await reminder_scheduler.stop(timeout=10.0)
            logger.info("Reminder scheduler stopped")
        except Exception as e:
            logger.error("Error stopping reminder scheduler", error=str(e), exc_info=True)
        finally:
            reminder_scheduler = None
    
    # Close database connections
    await close_db()
    logger.info("Database connections closed")


async def main():
    """Main application function"""
    
    # Load settings
    settings = get_settings()
    
    # Configure logging based on settings
    json_format = settings.log_format.lower() == "json"
    configure_logging(log_level=settings.log_level, json_format=json_format)
    logger.info("Logging configured", log_level=settings.log_level, format=settings.log_format)
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    global reminder_scheduler
    reminder_scheduler = ReminderScheduler(bot)
    
    # Use MemoryStorage for FSM (can be replaced with Redis for production)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register middlewares (order matters!)
    # 0. Error handler - must be first to catch all errors
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    
    # 1. Database session - provides session to all handlers
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    
    # 2. Authentication - checks user authorization
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # 3. I18n - provides translation function
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())
    
    # Register routers
    dp.include_router(start.router)
    dp.include_router(common.router)
    dp.include_router(health.router)
    dp.include_router(user_settings.router)
    dp.include_router(calendar.router)
    dp.include_router(booking.router)
    dp.include_router(mechanic.router)
    dp.include_router(admin.router)
    
    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Register global error handler for unhandled exceptions
    from aiogram.exceptions import (
        TelegramAPIError,
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramUnauthorizedError,
        TelegramConflictError,
        TelegramNetworkError,
        TelegramServerError,
    )
    
    @dp.errors()
    async def global_error_handler(update: Update, exception: Exception):
        """
        Global error handler for unhandled exceptions
        This catches errors that weren't handled by middleware
        """
        from aiogram.types import Message, CallbackQuery
        
        # Log the error
        logger.error(
            "Unhandled exception in dispatcher",
            error=str(exception),
            error_type=type(exception).__name__,
            update_type=update.event_type if hasattr(update, 'event_type') else None,
            exc_info=True
        )
        
        # Handle critical errors that should stop the bot
        if isinstance(exception, (TelegramUnauthorizedError, TelegramConflictError)):
            logger.critical("Critical error - stopping bot", error=str(exception))
            raise  # Re-raise to stop the bot
        
        # Try to send error message to user if possible
        try:
            event = update.event if hasattr(update, 'event') else None
            if isinstance(event, (Message, CallbackQuery)):
                from app.core.i18n import get_text
                from app.config.settings import get_settings
                
                settings = get_settings()
                language = settings.supported_languages_list[0] if settings.supported_languages_list else "pl"
                error_text = get_text("errors.unknown", language)
                
                if isinstance(event, Message):
                    await event.answer(error_text)
                elif isinstance(event, CallbackQuery):
                    if isinstance(event.message, Message):
                        await event.message.answer(error_text)
                    await event.answer()
        except Exception as e:
            logger.debug("Failed to send error message in global handler", error=str(e))
        
        return True  # Suppress the exception
    
    # Start polling
    reminder_scheduler.start()
    
    try:
        logger.info("Starting polling")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error("Error during polling", error=str(e), exc_info=True)
        raise
    finally:
        await bot.session.close()
        logger.info("Bot session closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)

