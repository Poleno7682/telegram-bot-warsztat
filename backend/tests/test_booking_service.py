"""Safety-net tests for BookingService core workflow.

These tests exist to catch regressions while executing the refactoring plan
in docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md (Phase 0). They cover the
booking lifecycle: create -> accept/reject -> propose new time -> confirm,
plus cancellation, without touching Telegram/aiogram at all.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone_utils import get_local_timezone
from app.models.booking import BookingStatus
from app.models.service import Service
from app.models.user import User, UserRole
from app.services.booking_service import BookingService


@pytest.fixture
def tomorrow_10am() -> datetime:
    """Deterministic future slot (tomorrow 10:00 local), inside default 08:00-16:00 work hours."""
    tz = get_local_timezone()
    tomorrow = (datetime.now(tz) + timedelta(days=1)).date()
    naive = datetime.combine(tomorrow, datetime.min.time()).replace(hour=10)
    return tz.localize(naive)


@pytest.fixture
async def creator(db_session: AsyncSession) -> User:
    user = User(telegram_id=1001, first_name="Creator", role=UserRole.USER, language="ru")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def mechanic(db_session: AsyncSession) -> User:
    user = User(telegram_id=2002, first_name="Mechanic", role=UserRole.MECHANIC, language="pl")
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
    """create_booking() must not hit the network translation API in tests."""

    async def fake_translate(text, source_lang, target_languages=None):
        return {"pl": text, "ru": text}

    monkeypatch.setattr(
        "app.services.booking_service.translate_to_all_languages", fake_translate
    )


async def make_booking(db_session, creator, service, when, **overrides):
    booking_service = BookingService(db_session)
    fields = dict(
        creator_telegram_id=creator.telegram_id,
        service_id=service.id,
        car_brand="Toyota",
        car_model="Corolla",
        car_number="WA12345",
        client_name="Jan Kowalski",
        client_phone="+48123456789",
        description="Stuk w silniku",
        language="pl",
        booking_datetime=when,
    )
    fields.update(overrides)
    return await booking_service.create_booking(**fields)


class TestCreateBooking:
    async def test_creates_booking_with_pending_status(self, db_session, creator, service, tomorrow_10am):
        booking, msg = await make_booking(db_session, creator, service, tomorrow_10am)

        assert booking is not None
        assert booking.status == BookingStatus.PENDING
        assert booking.creator_id == creator.id
        assert booking.service_id == service.id
        assert msg == "Booking created successfully"

    async def test_rejects_unknown_creator(self, db_session, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        booking, msg = await booking_service.create_booking(
            creator_telegram_id=99999,
            service_id=service.id,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA1",
            client_name="X",
            client_phone="+48000000000",
            description="",
            language="pl",
            booking_datetime=tomorrow_10am,
        )
        assert booking is None
        assert msg == "Creator not found"

    async def test_rejects_inactive_or_missing_service(self, db_session, creator, tomorrow_10am):
        booking_service = BookingService(db_session)
        booking, msg = await booking_service.create_booking(
            creator_telegram_id=creator.telegram_id,
            service_id=999999,
            car_brand="Toyota",
            car_model="Corolla",
            car_number="WA1",
            client_name="X",
            client_phone="+48000000000",
            description="",
            language="pl",
            booking_datetime=tomorrow_10am,
        )
        assert booking is None
        assert msg == "Service not found or inactive"

    async def test_rejects_double_booking_of_same_slot(self, db_session, creator, service, tomorrow_10am):
        first, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        assert first is not None

        second, msg = await make_booking(db_session, creator, service, tomorrow_10am)
        assert second is None
        assert msg == "Time slot is not available"


class TestAcceptRejectBooking:
    async def test_mechanic_can_accept_pending_booking(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        accepted, msg = await booking_service.accept_booking(created.id, mechanic.telegram_id)

        assert accepted is not None
        assert accepted.status == BookingStatus.ACCEPTED
        assert accepted.mechanic_id == mechanic.id
        assert msg == "Booking accepted"

    async def test_cannot_accept_already_accepted_booking(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        await booking_service.accept_booking(created.id, mechanic.telegram_id)

        result, msg = await booking_service.accept_booking(created.id, mechanic.telegram_id)

        assert result is None
        assert msg == "Booking is not in pending status"

    async def test_mechanic_can_reject_pending_booking(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        rejected, msg = await booking_service.reject_booking(created.id, mechanic.telegram_id)

        assert rejected is not None
        assert rejected.status == BookingStatus.REJECTED
        assert msg == "Booking rejected"


class TestTimeNegotiation:
    async def test_mechanic_can_propose_new_time(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        new_time = tomorrow_10am + timedelta(hours=2)

        proposed, msg = await booking_service.propose_new_time(created.id, mechanic.telegram_id, new_time)

        assert proposed is not None
        assert proposed.status == BookingStatus.NEGOTIATING
        assert proposed.proposed_date is not None
        assert msg == "New time proposed"

    async def test_creator_can_propose_new_time(self, db_session, creator, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        new_time = tomorrow_10am + timedelta(hours=2)

        proposed, msg = await booking_service.propose_new_time_by_user(created.id, creator.telegram_id, new_time)

        assert proposed is not None
        assert proposed.status == BookingStatus.NEGOTIATING
        assert msg == "New time proposed by user"

    async def test_creator_cannot_propose_time_for_foreign_booking(
        self, db_session, creator, mechanic, service, tomorrow_10am
    ):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        new_time = tomorrow_10am + timedelta(hours=2)

        result, msg = await booking_service.propose_new_time_by_user(created.id, mechanic.telegram_id, new_time)

        assert result is None
        assert msg == "Unauthorized"

    async def test_creator_confirms_proposed_time(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)
        new_time = tomorrow_10am + timedelta(hours=2)
        await booking_service.propose_new_time(created.id, mechanic.telegram_id, new_time)

        confirmed, msg = await booking_service.confirm_proposed_time(created.id, creator.telegram_id)

        assert confirmed is not None
        assert confirmed.status == BookingStatus.ACCEPTED
        assert confirmed.proposed_date is None
        assert msg == "Time confirmed"

    async def test_cannot_confirm_without_pending_proposal(self, db_session, creator, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        result, msg = await booking_service.confirm_proposed_time(created.id, creator.telegram_id)

        assert result is None
        assert msg == "Booking is not in negotiating status"


class TestGetBookingsByDate:
    async def test_returns_bookings_on_target_date_only(self, db_session, creator, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        same_day = await booking_service.get_bookings_by_date(tomorrow_10am.date())
        other_day = await booking_service.get_bookings_by_date(tomorrow_10am.date() + timedelta(days=5))

        assert [b.id for b in same_day] == [created.id]
        assert other_day == []


class TestCancelBooking:
    async def test_creator_can_cancel_own_booking(self, db_session, creator, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        success, msg = await booking_service.cancel_booking(created.id, creator.telegram_id)

        assert success is True
        assert msg == "Booking cancelled"

    async def test_stranger_cannot_cancel_booking(self, db_session, creator, mechanic, service, tomorrow_10am):
        booking_service = BookingService(db_session)
        created, _ = await make_booking(db_session, creator, service, tomorrow_10am)

        success, msg = await booking_service.cancel_booking(created.id, mechanic.telegram_id)

        assert success is False
        assert msg == "Unauthorized"
