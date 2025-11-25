"""Tests for RateLimiter"""

import pytest
import asyncio
from app.core.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_messages():
    """Test that rate limiter allows messages within limit"""
    limiter = RateLimiter(max_messages=5, time_window=60.0)
    
    chat_id = 12345
    
    # First 5 messages should be allowed
    for i in range(5):
        assert await limiter.is_allowed(chat_id) is True
        await limiter.record_message(chat_id)
    
    # 6th message should be rate limited
    assert await limiter.is_allowed(chat_id) is False


@pytest.mark.asyncio
async def test_rate_limiter_reset():
    """Test rate limiter reset"""
    limiter = RateLimiter(max_messages=2, time_window=60.0)
    
    chat_id = 12345
    
    # Exceed limit
    await limiter.record_message(chat_id)
    await limiter.record_message(chat_id)
    assert await limiter.is_allowed(chat_id) is False
    
    # Reset
    await limiter.reset(chat_id)
    assert await limiter.is_allowed(chat_id) is True


@pytest.mark.asyncio
async def test_rate_limiter_get_remaining():
    """Test getting remaining messages"""
    limiter = RateLimiter(max_messages=5, time_window=60.0)
    
    chat_id = 12345
    
    # Initially all messages available
    assert limiter.get_remaining(chat_id) == 5
    
    # After recording one message
    await limiter.record_message(chat_id)
    assert limiter.get_remaining(chat_id) == 4

