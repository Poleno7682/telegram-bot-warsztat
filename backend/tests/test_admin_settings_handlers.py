"""Regression tests for item 2.4.6 in docs/REFACTORING_PLAN_2026-07.md:
the work-hours/time-step/buffer-time input handlers in
bot/handlers/admin/settings.py only caught ValueError. A non-ValueError
failure (e.g. a DB error from SettingsManagementService) would propagate
without ever clearing the FSM state, leaving the user stuck being asked
for the same input forever.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.admin.settings import time_step_entered
from app.bot.states.booking import SettingsStates


def translate(key: str, **kwargs) -> str:
    return key


@pytest.fixture
async def fsm_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=100, user_id=100)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(SettingsStates.updating_time_step)
    return state


@pytest.fixture(autouse=True)
def no_background_menu_scheduling(monkeypatch):
    monkeypatch.setattr(
        "app.bot.handlers.admin.settings.schedule_main_menu_return",
        MagicMock(),
    )


class TestTimeStepEnteredErrorHandling:
    async def test_db_failure_still_clears_fsm_state(self, fsm_state, monkeypatch):
        mock_service = MagicMock()
        mock_service.update_time_step = AsyncMock(side_effect=RuntimeError("db is down"))
        monkeypatch.setattr(
            "app.bot.handlers.admin.settings.SettingsManagementService",
            MagicMock(return_value=mock_service),
        )

        message = MagicMock()
        message.text = "15"
        message.answer = AsyncMock()
        message.bot = MagicMock()
        user = MagicMock()

        await time_step_entered(
            message=message,
            session=MagicMock(),
            _=translate,
            state=fsm_state,
            user=user,
        )

        assert await fsm_state.get_state() is None
        message.answer.assert_awaited_once_with("errors.unknown")

    async def test_invalid_input_keeps_state_for_retry(self, fsm_state):
        message = MagicMock()
        message.text = "not a number"
        message.answer = AsyncMock()
        message.bot = MagicMock()
        user = MagicMock()

        await time_step_entered(
            message=message,
            session=MagicMock(),
            _=translate,
            state=fsm_state,
            user=user,
        )

        # Bad input should let the user retry, not silently kick them out
        # of the flow.
        assert await fsm_state.get_state() == SettingsStates.updating_time_step
        message.answer.assert_awaited_once_with("errors.invalid_input")
