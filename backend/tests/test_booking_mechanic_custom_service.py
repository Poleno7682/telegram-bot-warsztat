"""Tests for the mechanic-only "type a custom service instead of picking
from the catalog" booking-creation path.

Mechanics get a different first step (entering_custom_service_name /
entering_custom_duration) than the regular selecting_service flow, then
rejoin the standard flow via the same _advance_to_date_selection tail that
service_selected (the catalog path) uses - see bot/handlers/booking.py.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.booking import (
    _create_booking_and_respond,
    custom_duration_entered,
    custom_service_name_entered,
    start_new_booking,
)
from app.bot.states.booking import BookingStates
from app.core.timezone_utils import get_local_timezone
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

    # Two separate import sites need patching: the custom-service name
    # translation (this module) and BookingService.create_booking's own
    # description translation (used by the end-to-end flow test below).
    monkeypatch.setattr(
        "app.bot.handlers.booking.translate_to_all_languages", fake_translate
    )
    monkeypatch.setattr(
        "app.services.booking_service.translate_to_all_languages", fake_translate
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
    async def test_creates_active_service_and_advances_to_date_selection(
        self, db_session: AsyncSession, fsm_state
    ):
        """The service must be created ACTIVE at this point.
        BookingService.create_booking (called much later, once date/time/
        car/client info is collected) rejects service.is_active=False
        outright with "Service not found or inactive" - a real bug hit in
        production: the first cut of this feature deactivated the service
        immediately here, which meant a mechanic could go through the
        entire flow and then have booking creation fail at the very last
        step. Deactivation now happens only after the booking is actually
        created - see TestCreateBookingAndRespondDeactivatesCustomService.
        """
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
        assert data["is_custom_service"] is True

        repo = ServiceRepository(db_session)
        service = await repo.get_by_id(service_id)
        assert service is not None
        assert service.name_pl == "Замена масла"
        assert service.name_ru == "Замена масла"
        assert service.duration_minutes == 45
        assert service.is_active is True

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


class TestFullCustomServiceBookingFlow:
    async def test_booking_is_created_and_service_deactivated_afterward(
        self, db_session: AsyncSession, fsm_state
    ):
        """End-to-end regression test for the production bug: a mechanic
        types a service + duration, then completes the rest of the
        booking flow, and the booking must actually be created (it wasn't
        - creation failed with "Service not found or inactive" because
        the service was deactivated too early). The service should only
        become inactive once the booking exists.
        """
        mechanic = User(telegram_id=600, first_name="Mechanic", role=UserRole.MECHANIC, language="ru")
        db_session.add(mechanic)
        await db_session.commit()
        await db_session.refresh(mechanic)

        await fsm_state.set_state(BookingStates.entering_custom_duration)
        await fsm_state.update_data(custom_service_name="Замена масла")

        duration_message = MagicMock(spec=Message)
        duration_message.text = "45"
        duration_message.answer = AsyncMock()

        await custom_duration_entered(
            message=duration_message,
            session=db_session,
            _=translate,
            state=fsm_state,
            language="ru",
        )
        assert await fsm_state.get_state() == BookingStates.selecting_date

        data = await fsm_state.get_data()
        service_id = data["service_id"]

        # Fast-forward through date/time/car/client entry (each already
        # covered by its own tests elsewhere) directly via state data, the
        # same shape _create_booking_and_respond expects.
        tz = get_local_timezone()
        tomorrow = datetime.now(tz) + timedelta(days=1)
        booking_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
        await fsm_state.update_data(
            booking_time=booking_time,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA12345",
            client_name="Jan Kowalski",
            client_phone="+48123456789",
        )

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()

        result_message = MagicMock(spec=Message)
        result_message.edit_text = AsyncMock()
        result_message.answer = AsyncMock()

        await _create_booking_and_respond(
            session=db_session,
            user=mechanic,
            state=fsm_state,
            description="",
            bot=mock_bot,
            _=translate,
            language="ru",
            send_translating_message=lambda: result_message.answer("translating"),
            show_result=result_message.edit_text,
            answer=result_message.answer,
            chat_id=mechanic.telegram_id,
        )

        # The actual regression: booking creation must succeed, not fail
        # with "errors.unknown" / "booking.confirm.error" because the
        # service was already inactive.
        result_message.edit_text.assert_awaited_once()
        shown_text = result_message.edit_text.await_args.args[0]
        assert "booking.confirm.error" not in shown_text
        assert "errors.unknown" not in shown_text

        repo = ServiceRepository(db_session)
        service = await repo.get_by_id(service_id)
        assert service is not None
        # Deactivated now that the booking exists, so it doesn't linger
        # in the regular catalog.
        assert service.is_active is False
