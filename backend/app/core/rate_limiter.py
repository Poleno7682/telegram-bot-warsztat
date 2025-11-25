"""Rate Limiter - prevents spam by throttling messages per chat"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter to prevent message spam per chat"""
    
    def __init__(
        self,
        max_messages: int = 5,
        time_window: float = 60.0
    ):
        """
        Initialize rate limiter
        
        Args:
            max_messages: Maximum number of messages allowed in time window
            time_window: Time window in seconds
        """
        self.max_messages = max_messages
        self.time_window = timedelta(seconds=time_window)
        
        # Track message timestamps per chat_id
        self._message_times: Dict[int, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, chat_id: int) -> bool:
        """
        Check if message is allowed (not rate limited)
        
        Args:
            chat_id: Chat ID
            
        Returns:
            True if message is allowed, False if rate limited
        """
        async with self._lock:
            now = datetime.now()
            times = self._message_times[chat_id]
            
            # Remove old timestamps outside time window
            cutoff = now - self.time_window
            times[:] = [t for t in times if t > cutoff]
            
            # Check if limit exceeded
            if len(times) >= self.max_messages:
                logger.warning(
                    f"Rate limit exceeded for chat {chat_id}: "
                    f"{len(times)} messages in {self.time_window.total_seconds()}s"
                )
                return False
            
            return True
    
    async def record_message(self, chat_id: int) -> None:
        """
        Record that a message was sent
        
        Args:
            chat_id: Chat ID
        """
        async with self._lock:
            now = datetime.now()
            self._message_times[chat_id].append(now)
            
            # Clean up old entries periodically
            if len(self._message_times[chat_id]) > self.max_messages * 2:
                cutoff = now - self.time_window
                self._message_times[chat_id] = [
                    t for t in self._message_times[chat_id] if t > cutoff
                ]
    
    async def reset(self, chat_id: Optional[int] = None) -> None:
        """
        Reset rate limit for a chat or all chats
        
        Args:
            chat_id: Chat ID to reset, or None to reset all
        """
        async with self._lock:
            if chat_id is None:
                self._message_times.clear()
            elif chat_id in self._message_times:
                del self._message_times[chat_id]
    
    def get_remaining(self, chat_id: int) -> int:
        """
        Get remaining messages allowed in current time window
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Number of remaining messages
        """
        now = datetime.now()
        cutoff = now - self.time_window
        times = [t for t in self._message_times[chat_id] if t > cutoff]
        return max(0, self.max_messages - len(times))


# Global instances for different rate limiters
_notification_rate_limiter: Optional[RateLimiter] = None
_translation_rate_limiter: Optional[RateLimiter] = None


def get_notification_rate_limiter() -> RateLimiter:
    """Get rate limiter for notifications (5 messages per 60 seconds)"""
    global _notification_rate_limiter
    if _notification_rate_limiter is None:
        _notification_rate_limiter = RateLimiter(max_messages=5, time_window=60.0)
    return _notification_rate_limiter


def get_translation_rate_limiter() -> RateLimiter:
    """Get rate limiter for translation errors (3 messages per 60 seconds)"""
    global _translation_rate_limiter
    if _translation_rate_limiter is None:
        _translation_rate_limiter = RateLimiter(max_messages=3, time_window=60.0)
    return _translation_rate_limiter

