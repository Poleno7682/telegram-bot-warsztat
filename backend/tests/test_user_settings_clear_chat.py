"""Tests for the "🧹 Очистить чат" button added to the user settings menu.

clear_chat_ask shows a Yes/No confirmation (clearing chat history is
irreversible); clear_chat_do actually wipes it via
app.bot.ui.chat_cleaner.clear_chat_history (tested in isolation in
test_chat_cleaner.py) and rewrites the surviving message into the
settings screen.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.user_settings import clear_chat_ask, clear_chat_confirmed
from app.models.user import User, UserRole


def translate(key: str, **kwargs) -> str:
    return key


def make_callback_with_message() -> tuple[MagicMock, MagicMock]:
    message = MagicMock(spec=Message)
    message.edit_text = AsyncMock()
    message.chat = MagicMock(id=777)
    message.message_id = 999

    callback = MagicMock(spec=CallbackQuery)
    callback.message = message
    callback.answer = AsyncMock()
    callback.bot = AsyncMock()
    return callback, message


class TestClearChatAsk:
    async def test_shows_yes_no_confirmation(self):
        callback, message = make_callback_with_message()

        await clear_chat_ask(callback=callback, _=translate)

        message.edit_text.assert_awaited_once()
        text, kwargs = message.edit_text.await_args.args, message.edit_text.await_args.kwargs
        assert text[0] == "user_settings.clear_chat_confirm"
        keyboard = kwargs["reply_markup"]
        callback_datas = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        assert "user_settings:clear_chat_do" in callback_datas
        assert "menu:user_settings" in callback_datas

    async def test_noop_without_editable_message(self):
        callback = MagicMock(spec=CallbackQuery)
        callback.message = None
        callback.answer = AsyncMock()

        await clear_chat_ask(callback=callback, _=translate)

        callback.answer.assert_awaited_once()


class TestClearChatConfirmed:
    async def test_clears_history_and_rewrites_current_message(self, monkeypatch):
        clear_mock = AsyncMock(return_value=12)
        monkeypatch.setattr(
            "app.bot.handlers.user_settings.clear_chat_history", clear_mock
        )
        callback, message = make_callback_with_message()
        user = User(telegram_id=1, first_name="Test", role=UserRole.USER, language="ru")

        await clear_chat_confirmed(callback=callback, user=user, _=translate)

        clear_mock.assert_awaited_once_with(callback.bot, 777, 999)
        message.edit_text.assert_awaited_once()
        shown_text = message.edit_text.await_args.args[0]
        assert "user_settings.clear_chat_done" in shown_text
        assert "user_settings.info" in shown_text
        callback.answer.assert_awaited_once()

    async def test_noop_without_bot_or_message(self):
        callback = MagicMock(spec=CallbackQuery)
        callback.message = None
        callback.bot = None
        callback.answer = AsyncMock()
        user = User(telegram_id=1, first_name="Test", role=UserRole.USER, language="ru")

        await clear_chat_confirmed(callback=callback, user=user, _=translate)

        callback.answer.assert_awaited_once()
