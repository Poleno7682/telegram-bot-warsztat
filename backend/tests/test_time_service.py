"""Regression tests for TimeService.is_slot_available / calculate_available_slots.

Covers the exclude_booking_id bug from docs/REFACTORING_PLAN_2026-07.md (0.2):
exclude_booking_id was accepted by is_slot_available but never actually
threaded through to calculate_available_slots, so rescheduling a booking to
a nearby slot was always rejected as "unavailable" because the booking's own
occupied slot was still counted against it.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone_utils import get_local_timezone
from app.models.service import Service
from app.models.user import User, UserRole
from app.services.booking_service import BookingService
from app.services.time_service import TimeService


@pytest.fixture
def tomorrow_10am() -> datetime:
    tz = get_local_timezone()
    tomorrow = (datetime.now(tz) + timedelta(days=1)).date()
    naive = datetime.combine(tomorrow, datetime.min.time()).replace(hour=10)
    return tz.localize(naive)


@pytest.fixture
async def creator(db_session: AsyncSession) -> User:
    user = User(telegram_id=3001, first_name="Creator", role=UserRole.USER, language="ru")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def service(db_session: AsyncSession) -> Service:
    svc = Service(
        name_pl="Wymiana oleju",
        name_ru="Замена масла",
        duration_minutes=30,
        is_active=True,
    )
    db_session.add(svc)
    await db_session.commit()
    await db_session.refresh(svc)
    return svc


@pytest.fixture(autouse=True)
def no_real_translation(monkeypatch):
    async def fake_translate(text, source_lang, target_languages=None):
        return {"pl": text, "ru": text}

    monkeypatch.setattr(
        "app.services.booking_service.translate_to_all_languages", fake_translate
    )


class TestExcludeBookingId:
    async def test_own_slot_unavailable_without_exclude(
        self, db_session, creator, service, tomorrow_10am
    ):
        booking_service = BookingService(db_session)
        booking, msg = await booking_service.create_booking(
            creator_telegram_id=creator.telegram_id,
            service_id=service.id,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA12345",
            client_name="Jan Kowalski",
            client_phone="+48123456789",
            description="Stuk w silniku",
            language="pl",
            booking_datetime=tomorrow_10am,
        )
        assert booking is not None, msg

        time_service = TimeService(db_session)
        # Without exclude_booking_id, the booking's own slot blocks itself.
        assert (
            await time_service.is_slot_available(tomorrow_10am, service.duration_minutes)
        ) is False

    async def test_own_slot_available_with_exclude(
        self, db_session, creator, service, tomorrow_10am
    ):
        booking_service = BookingService(db_session)
        booking, msg = await booking_service.create_booking(
            creator_telegram_id=creator.telegram_id,
            service_id=service.id,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA12345",
            client_name="Jan Kowalski",
            client_phone="+48123456789",
            description="Stuk w silniku",
            language="pl",
            booking_datetime=tomorrow_10am,
        )
        assert booking is not None, msg

        time_service = TimeService(db_session)
        assert (
            await time_service.is_slot_available(
                tomorrow_10am, service.duration_minutes, exclude_booking_id=booking.id
            )
        ) is True

    async def test_exclude_does_not_free_other_bookings_slot(
        self, db_session, creator, service, tomorrow_10am
    ):
        booking_service = BookingService(db_session)
        booking_a, msg_a = await booking_service.create_booking(
            creator_telegram_id=creator.telegram_id,
            service_id=service.id,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA12345",
            client_name="Jan Kowalski",
            client_phone="+48123456789",
            description="A",
            language="pl",
            booking_datetime=tomorrow_10am,
        )
        assert booking_a is not None, msg_a

        second_slot = tomorrow_10am + timedelta(minutes=60)
        booking_b, msg_b = await booking_service.create_booking(
            creator_telegram_id=creator.telegram_id,
            service_id=service.id,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA12346",
            client_name="Jan Kowalski",
            client_phone="+48123456789",
            description="B",
            language="pl",
            booking_datetime=second_slot,
        )
        assert booking_b is not None, msg_b

        time_service = TimeService(db_session)
        # Excluding booking A must not make booking B's own slot available.
        assert (
            await time_service.is_slot_available(
                second_slot, service.duration_minutes, exclude_booking_id=booking_a.id
            )
        ) is False
