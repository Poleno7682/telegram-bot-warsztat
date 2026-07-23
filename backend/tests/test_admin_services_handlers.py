"""Regression test for item 2.4.8 in docs/REFACTORING_PLAN_2026-07.md:
service_duration_entered gave no feedback and left the FSM state stuck if
create_service failed, unlike the symmetric user/mechanic add flows.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.admin.services import service_duration_entered
from app.bot.states.booking import AddServiceStates


def translate(key: str, **kwargs) -> str:
    return key


@pytest.fixture
async def fsm_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=200, user_id=200)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(AddServiceStates.entering_duration)
    await state.update_data(name_pl="Test PL", name_ru="Test RU")
    return state


@pytest.fixture(autouse=True)
def no_background_menu_scheduling(monkeypatch):
    monkeypatch.setattr(
        "app.bot.handlers.admin.services.schedule_main_menu_return",
        MagicMock(),
    )


class TestServiceDurationEnteredErrorHandling:
    async def test_db_failure_notifies_user_and_clears_state(self, fsm_state, monkeypatch):
        mock_service = MagicMock()
        mock_service.create_service = AsyncMock(side_effect=RuntimeError("db is down"))
        monkeypatch.setattr(
            "app.bot.handlers.admin.services.ServiceManagementService",
            MagicMock(return_value=mock_service),
        )

        message = MagicMock()
        message.text = "30"
        message.answer = AsyncMock()
        message.bot = MagicMock()
        user = MagicMock()

        await service_duration_entered(
            message=message,
            session=MagicMock(),
            _=translate,
            state=fsm_state,
            user=user,
        )

        assert await fsm_state.get_state() is None
        message.answer.assert_awaited_once_with("errors.unknown")

    async def test_success_notifies_user_and_clears_state(self, fsm_state, monkeypatch):
        fake_service = MagicMock()
        mock_service = MagicMock()
        mock_service.create_service = AsyncMock(return_value=fake_service)
        monkeypatch.setattr(
            "app.bot.handlers.admin.services.ServiceManagementService",
            MagicMock(return_value=mock_service),
        )

        message = MagicMock()
        message.text = "30"
        message.answer = AsyncMock()
        message.bot = MagicMock()
        user = MagicMock()

        await service_duration_entered(
            message=message,
            session=MagicMock(),
            _=translate,
            state=fsm_state,
            user=user,
        )

        assert await fsm_state.get_state() is None
        message.answer.assert_awaited_once_with("service_management.service_added")
