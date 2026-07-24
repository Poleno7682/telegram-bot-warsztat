"""Tests for clear_chat_history (app/bot/ui/chat_cleaner.py) - the "Clear
chat" button added to the user settings menu.

Telegram's Bot API has no bulk "clear chat" endpoint, so this walks
message_id backwards from a known id, deleting each one and tolerating
failures (message doesn't exist / already deleted / too old to delete),
which is the normal case for most of the range.
"""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.bot.ui.chat_cleaner import (
    MAX_CONSECUTIVE_FAILURES,
    MAX_LOOKBACK,
    clear_chat_history,
)


def make_bad_request(text: str = "message to delete not found") -> TelegramBadRequest:
    return TelegramBadRequest(method=None, message=text)


class TestClearChatHistory:
    async def test_deletes_every_message_except_the_kept_one(self):
        bot = AsyncMock()
        bot.delete_message = AsyncMock()
        keep_message_id = 100

        deleted = await clear_chat_history(bot, chat_id=1, keep_message_id=keep_message_id)

        deleted_ids = [call.args[1] for call in bot.delete_message.await_args_list]
        assert keep_message_id not in deleted_ids
        assert deleted == len(deleted_ids)
        # Every attempt succeeded, so it must have walked the whole
        # available range down to message_id 1.
        assert deleted_ids[0] == keep_message_id - 1
        assert deleted_ids[-1] == 1

    async def test_stops_early_after_consecutive_failures(self):
        bot = AsyncMock()
        bot.delete_message = AsyncMock(side_effect=make_bad_request())
        keep_message_id = 100_000  # far larger than MAX_CONSECUTIVE_FAILURES

        deleted = await clear_chat_history(bot, chat_id=1, keep_message_id=keep_message_id)

        assert deleted == 0
        # Must give up well before exhausting MAX_LOOKBACK.
        assert bot.delete_message.await_count == MAX_CONSECUTIVE_FAILURES
        assert bot.delete_message.await_count < MAX_LOOKBACK

    async def test_forbidden_error_stops_immediately(self):
        bot = AsyncMock()
        bot.delete_message = AsyncMock(side_effect=TelegramForbiddenError(method=None, message="bot was blocked"))

        deleted = await clear_chat_history(bot, chat_id=1, keep_message_id=50)

        assert deleted == 0
        bot.delete_message.assert_awaited_once()

    async def test_retry_after_is_honored_then_deletion_continues(self, monkeypatch):
        sleep_mock = AsyncMock()
        monkeypatch.setattr("app.bot.ui.chat_cleaner.asyncio.sleep", sleep_mock)

        bot = AsyncMock()
        bot.delete_message = AsyncMock(
            side_effect=[
                TelegramRetryAfter(method=None, message="flood", retry_after=3),
                None,  # retry succeeds
                make_bad_request(),
            ]
        )

        # keep_message_id=3 bounds the walk to exactly message_id 2 (the
        # retry-after case, 2 mock calls) then message_id 1 (1 mock call)
        # - matching the 3-item side_effect list exactly.
        deleted = await clear_chat_history(bot, chat_id=1, keep_message_id=3)

        sleep_mock.assert_awaited_once_with(3)
        assert deleted == 1
        assert bot.delete_message.await_count == 3

    async def test_consecutive_failure_streak_resets_on_success(self):
        """A single success partway through must reset the failure
        counter, not let unrelated earlier failures count towards the
        early-stop threshold."""
        success_at_call = MAX_CONSECUTIVE_FAILURES
        call_count = 0

        async def flaky_delete(chat_id, message_id):
            nonlocal call_count
            call_count += 1
            if call_count == success_at_call:
                return None
            raise make_bad_request()

        bot = AsyncMock()
        bot.delete_message = AsyncMock(side_effect=flaky_delete)

        deleted = await clear_chat_history(bot, chat_id=1, keep_message_id=100_000)

        assert deleted == 1
        # Without the streak reset, it would have stopped after exactly
        # MAX_CONSECUTIVE_FAILURES calls (all failures). With the reset,
        # it must run MAX_CONSECUTIVE_FAILURES *more* failing calls after
        # the one success before giving up.
        assert call_count == success_at_call + MAX_CONSECUTIVE_FAILURES
