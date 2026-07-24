"""Chat history clearing.

Telegram's Bot API has no bulk "clear chat" endpoint. message_id is
sequential per chat and shared between the bot's own messages and the
user's, so the standard trick (used by most "clear chat" Telegram bots) is
to walk backwards from a known message_id and try deleting each one,
ignoring the ones that fail (too old to delete, already gone, or never
existed as a real message).

In app.bot.ui (not app.bot.handlers) for the same reason as menu.py: it's
plain Bot-API logic with no handler-specific state, safe to import from
anywhere without pulling in the handlers package.
"""

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# How far back to walk before giving up even if messages are still being
# found - a hard ceiling so a very long chat history can't turn this into
# thousands of API calls.
MAX_LOOKBACK = 5000

# Stop early once this many consecutive delete attempts fail - past this
# point we're almost certainly deleting into messages older than the 48h
# window bots are allowed to delete, or past the start of the chat.
MAX_CONSECUTIVE_FAILURES = 50


async def clear_chat_history(bot: Bot, chat_id: int, keep_message_id: int) -> int:
    """
    Delete every message in the chat except keep_message_id.

    Args:
        bot: Bot instance
        chat_id: Chat to clear
        keep_message_id: The one message_id that must survive (typically
            the menu message the "Clear chat" button itself lives on)

    Returns:
        Number of messages actually deleted
    """
    deleted = 0
    consecutive_failures = 0
    lower_bound = max(keep_message_id - MAX_LOOKBACK, 0)

    for message_id in range(keep_message_id - 1, lower_bound, -1):
        try:
            await bot.delete_message(chat_id, message_id)
            deleted += 1
            consecutive_failures = 0
            continue
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.delete_message(chat_id, message_id)
                deleted += 1
                consecutive_failures = 0
                continue
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
        except TelegramForbiddenError:
            # Bot was blocked/kicked mid-clear - nothing more we can do.
            break
        except TelegramBadRequest:
            # Expected for most of the range: message doesn't exist,
            # already deleted, or too old (>48h) to delete.
            pass

        consecutive_failures += 1
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.debug(
                "Stopping chat clear early after consecutive delete failures",
                chat_id=chat_id,
                deleted=deleted,
            )
            break

    return deleted
