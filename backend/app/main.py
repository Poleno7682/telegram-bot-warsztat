"""Main application entry point"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.settings import get_settings
from app.config.database import init_db, close_db
from app.bot.handlers import start, common, booking, mechanic, admin, user_settings
from app.bot.middlewares import DbSessionMiddleware, AuthMiddleware, I18nMiddleware


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Actions to perform on startup"""
    logger.info("Starting bot...")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")


async def on_shutdown(bot: Bot):
    """Actions to perform on shutdown"""
    logger.info("Shutting down bot...")
    
    # Close database connections
    await close_db()
    logger.info("Database connections closed")


async def main():
    """Main application function"""
    
    # Load settings
    settings = get_settings()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Use MemoryStorage for FSM (can be replaced with Redis for production)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register middlewares (order matters!)
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
    dp.include_router(user_settings.router)
    dp.include_router(booking.router)
    dp.include_router(mechanic.router)
    dp.include_router(admin.router)
    
    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Error during polling: {e}")
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

