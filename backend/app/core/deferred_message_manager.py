"""Deferred Message Manager - prevents duplicate scheduled messages"""

import asyncio
import logging
from typing import Dict, Optional, Callable, Awaitable
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import Message as TelegramMessage

logger = logging.getLogger(__name__)


class DeferredMessageManager:
    """Manages deferred messages to prevent duplicates per chat"""
    
    def __init__(self):
        """Initialize deferred message manager"""
        # Track scheduled tasks by chat_id
        self._scheduled_tasks: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def schedule_message(
        self,
        bot: Bot,
        chat_id: int,
        message_func: Callable[[], Awaitable[TelegramMessage | None]],
        delay: float = 3.0,
        cancel_previous: bool = True
    ) -> None:
        """
        Schedule a message to be sent after delay
        
        Args:
            bot: Bot instance
            chat_id: Chat ID to send message to
            message_func: Async function that sends the message
            delay: Delay in seconds before sending
            cancel_previous: Whether to cancel previous scheduled message for this chat
        """
        async with self._lock:
            # Cancel previous task for this chat if requested
            if cancel_previous and chat_id in self._scheduled_tasks:
                task = self._scheduled_tasks[chat_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    logger.debug(f"Cancelled previous scheduled message for chat {chat_id}")
            
            # Create new task
            async def _send_message():
                try:
                    await asyncio.sleep(delay)
                    await message_func()
                    logger.debug(f"Sent deferred message to chat {chat_id}")
                except asyncio.CancelledError:
                    logger.debug(f"Deferred message for chat {chat_id} was cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Error sending deferred message to chat {chat_id}: {e}")
                finally:
                    # Clean up task reference
                    async with self._lock:
                        if chat_id in self._scheduled_tasks:
                            task = self._scheduled_tasks[chat_id]
                            if task.done():
                                del self._scheduled_tasks[chat_id]
            
            task = asyncio.create_task(_send_message())
            self._scheduled_tasks[chat_id] = task
    
    async def cancel_message(self, chat_id: int) -> bool:
        """
        Cancel scheduled message for a chat
        
        Args:
            chat_id: Chat ID
            
        Returns:
            True if message was cancelled, False if no message was scheduled
        """
        async with self._lock:
            if chat_id not in self._scheduled_tasks:
                return False
            
            task = self._scheduled_tasks[chat_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.debug(f"Cancelled scheduled message for chat {chat_id}")
            
            del self._scheduled_tasks[chat_id]
            return True
    
    async def cancel_all(self) -> None:
        """Cancel all scheduled messages"""
        async with self._lock:
            for chat_id, task in list(self._scheduled_tasks.items()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._scheduled_tasks.clear()
            logger.info("Cancelled all scheduled messages")
    
    def has_scheduled(self, chat_id: int) -> bool:
        """
        Check if there's a scheduled message for a chat
        
        Args:
            chat_id: Chat ID
            
        Returns:
            True if message is scheduled
        """
        if chat_id not in self._scheduled_tasks:
            return False
        task = self._scheduled_tasks[chat_id]
        return not task.done()


# Global singleton instance
_deferred_message_manager: Optional[DeferredMessageManager] = None


def get_deferred_message_manager() -> DeferredMessageManager:
    """Get singleton deferred message manager instance"""
    global _deferred_message_manager
    if _deferred_message_manager is None:
        _deferred_message_manager = DeferredMessageManager()
    return _deferred_message_manager

