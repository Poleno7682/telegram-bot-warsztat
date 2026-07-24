"""Tests for the mechanic-only "type a custom service instead of picking
from the catalog" booking-creation path.

Mechanics get a different first step (entering_custom_service_name /
entering_custom_duration) than the regular selecting_service flow, then
rejoin the standard flow via the same _advance_to_date_selection tail that
service_selected (the catalog path) uses - see bot/handlers/booking.py.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.booking import (
    custom_duration_entered,
    custom_service_name_entered,
    start_new_booking,
)
from app.bot.states.booking import BookingStates
from app.models.user import User, UserRole
from app.repositories.service import ServiceRepository


def translate(key: str, **kwargs) -> str:
    return key


@pytest.fixture
async def fsm_state() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=400, user_id=400)
    return FSMContext(storage=storage, key=key)


@pytest.fixture(autouse=True)
def no_real_translation(monkeypatch):
    async def fake_translate(text, source_lang, target_languages=None):
        return {"pl": text, "ru": text}

    monkeypatch.setattr(
        "app.bot.handlers.booking.translate_to_all_languages", fake_translate
    )


class TestMechanicSkipsServiceCatalog:
    async def test_mechanic_gets_custom_service_prompt(self, fsm_state):
        callback = MagicMock(spec=CallbackQuery)
        message = MagicMock(spec=Message)
        message.edit_text = AsyncMock()
        message.answer = AsyncMock()
        message.delete = AsyncMock()
        message.chat = MagicMock(id=400)
        callback.message = message
        callback.answer = AsyncMock()
        callback.bot = AsyncMock()
        mechanic = User(id=1, telegram_id=500, first_name="M", role=UserRole.MECHANIC)

        await start_new_booking(
            callback=callback,
            session=MagicMock(),
            user=mechanic,
            _=translate,
            state=fsm_state,
            language="ru",
        )

        assert await fsm_state.get_state() == BookingStates.entering_custom_service_name
        assert await fsm_state.get_state() != BookingStates.selecting_service

    async def test_regular_user_still_sees_catalog_flow(self, db_session: AsyncSession, fsm_state):
        callback = MagicMock(spec=CallbackQuery)
        message = MagicMock(spec=Message)
        message.edit_text = AsyncMock()
        message.answer = AsyncMock()
        message.delete = AsyncMock()
        message.chat = MagicMock(id=400)
        callback.message = message
        callback.answer = AsyncMock()
        callback.bot = AsyncMock()
        regular_user = User(id=2, telegram_id=501, first_name="U", role=UserRole.USER)

        repo = ServiceRepository(db_session)
        from app.dto import ServiceCreateData
        await repo.create_service(
            ServiceCreateData(name_pl="Test", name_ru="Тест", duration_minutes=30)
        )
        await db_session.commit()

        await start_new_booking(
            callback=callback,
            session=db_session,
            user=regular_user,
            _=translate,
            state=fsm_state,
            language="ru",
        )

        assert await fsm_state.get_state() == BookingStates.selecting_service


class TestCustomServiceNameEntered:
    async def test_stores_name_and_advances_to_duration_step(self, fsm_state):
        await fsm_state.set_state(BookingStates.entering_custom_service_name)
        message = MagicMock(spec=Message)
        message.text = "Замена масла, диагностика подвески"
        message.answer = AsyncMock()

        await custom_service_name_entered(message=message, _=translate, state=fsm_state)

        data = await fsm_state.get_data()
        assert data["custom_service_name"] == "Замена масла, диагностика подвески"
        assert await fsm_state.get_state() == BookingStates.entering_custom_duration

    async def test_empty_input_rejected(self, fsm_state):
        await fsm_state.set_state(BookingStates.entering_custom_service_name)
        message = MagicMock(spec=Message)
        message.text = "   "
        message.answer = AsyncMock()

        await custom_service_name_entered(message=message, _=translate, state=fsm_state)

        assert await fsm_state.get_state() == BookingStates.entering_custom_service_name
        message.answer.assert_awaited_once_with("errors.invalid_input")


class TestCustomDurationEntered:
    async def test_creates_inactive_service_and_advances_to_date_selection(
        self, db_session: AsyncSession, fsm_state
    ):
        await fsm_state.set_state(BookingStates.entering_custom_duration)
        await fsm_state.update_data(custom_service_name="Замена масла")

        message = MagicMock(spec=Message)
        message.text = "45"
        message.answer = AsyncMock()

        await custom_duration_entered(
            message=message,
            session=db_session,
            _=translate,
            state=fsm_state,
            language="ru",
        )

        data = await fsm_state.get_data()
        service_id = data["service_id"]
        assert isinstance(service_id, int)

        repo = ServiceRepository(db_session)
        service = await repo.get_by_id(service_id)
        assert service is not None
        assert service.name_pl == "Замена масла"
        assert service.name_ru == "Замена масла"
        assert service.duration_minutes == 45
        assert service.is_active is False

        # Custom services must never show up in the regular catalog.
        active = await repo.get_all_active()
        assert service_id not in [s.id for s in active]

        assert await fsm_state.get_state() == BookingStates.selecting_date

    async def test_invalid_duration_rejected(self, db_session: AsyncSession, fsm_state):
        await fsm_state.set_state(BookingStates.entering_custom_duration)
        await fsm_state.update_data(custom_service_name="Замена масла")

        message = MagicMock(spec=Message)
        message.text = "not a number"
        message.answer = AsyncMock()

        await custom_duration_entered(
            message=message,
            session=db_session,
            _=translate,
            state=fsm_state,
            language="ru",
        )

        assert await fsm_state.get_state() == BookingStates.entering_custom_duration
        message.answer.assert_awaited_once_with("errors.invalid_input")
