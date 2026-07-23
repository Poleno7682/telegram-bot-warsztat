"""Tests for the "Skip" button on the client-phone step of booking creation.

Reuses the same skip-keyboard/skip-callback pattern already used for the
optional description step (get_skip_keyboard + a "booking:skip_*" callback
handler scoped to the relevant FSM state) rather than inventing a new one -
get_skip_keyboard was parameterized to accept the target callback_data
instead of duplicating the whole keyboard-building function.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from app.bot.handlers.booking import NO_PHONE_PLACEHOLDER, skip_client_phone
from app.bot.keyboards.inline import get_skip_keyboard
from app.bot.states.booking import BookingStates


def translate(key: str, **kwargs) -> str:
    return key


@pytest.fixture
async def fsm_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=300, user_id=300)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(BookingStates.entering_client_phone)
    return state


class TestSkipClientPhone:
    async def test_stores_placeholder_and_advances_to_description_step(self, fsm_state):
        message = MagicMock(spec=Message)
        message.edit_text = AsyncMock()

        callback = MagicMock(spec=CallbackQuery)
        callback.message = message
        callback.answer = AsyncMock()

        await skip_client_phone(callback=callback, _=translate, state=fsm_state)

        data = await fsm_state.get_data()
        assert data["client_phone"] == NO_PHONE_PLACEHOLDER
        assert await fsm_state.get_state() == BookingStates.entering_description
        message.edit_text.assert_awaited_once()
        assert message.edit_text.await_args.args[0] == "booking.create.enter_description"
        callback.answer.assert_awaited_once()

    async def test_noop_without_editable_message(self, fsm_state):
        callback = MagicMock(spec=CallbackQuery)
        callback.message = None
        callback.answer = AsyncMock()

        await skip_client_phone(callback=callback, _=translate, state=fsm_state)

        # Nothing should have been written to state, and the FSM state
        # must stay put so the user isn't silently dropped from the flow.
        data = await fsm_state.get_data()
        assert "client_phone" not in data
        assert await fsm_state.get_state() == BookingStates.entering_client_phone
        callback.answer.assert_awaited_once()


def test_skip_keyboard_accepts_custom_callback_data():
    markup = get_skip_keyboard(translate, "booking:skip_phone")
    skip_button = markup.inline_keyboard[0][0]
    assert skip_button.callback_data == "booking:skip_phone"

    default_markup = get_skip_keyboard(translate)
    assert default_markup.inline_keyboard[0][0].callback_data == "booking:skip_description"
