"""Regression tests for ReminderScheduler._process_cycle.

Covers 0.4 from docs/REFACTORING_PLAN_2026-07.md: reminders used to be
marked as sent (sent_attr=True) unconditionally, even when delivery failed
(e.g. transient network error), so a failed reminder was silently lost and
never retried. It should only be marked sent when the notification was
actually delivered, or when the recipient is permanently unreachable
(blocked the bot) - retrying that forever would be pointless too.

ReminderScheduler._process_cycle opens its own session via the module-level
AsyncSessionLocal (app.config.database), independent of the db_session
fixture used elsewhere in this suite. To keep this a real integration test
(not a mock of the DB layer), we monkeypatch AsyncSessionLocal to point at
the same in-memory test engine.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.models.user import User, UserRole
from app.services.reminder_scheduler import ReminderScheduler

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def scheduler_session(monkeypatch):
    """A session bound to the same in-memory engine that ReminderScheduler
    will use internally (via a monkeypatched AsyncSessionLocal)."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.services.reminder_scheduler.AsyncSessionLocal", session_factory)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def make_due_booking(session: AsyncSession, minutes_until: int = 60):
    """Create an ACCEPTED booking with a mechanic, due in `minutes_until`
    minutes - inside the 1h reminder rule's send window (55-65 min).

    Built directly (bypassing BookingService.create_booking) since that
    enforces work-hours/slot-availability against the real current time,
    which this test doesn't care about - only reminder delivery tracking.
    """
    creator = User(telegram_id=5001, first_name="Creator", role=UserRole.USER, language="ru")
    mechanic = User(telegram_id=6002, first_name="Mechanic", role=UserRole.MECHANIC, language="pl")
    session.add_all([creator, mechanic])
    await session.commit()
    await session.refresh(creator)
    await session.refresh(mechanic)

    service = Service(name_pl="Wymiana oleju", name_ru="Замена масла", duration_minutes=30, is_active=True)
    session.add(service)
    await session.commit()
    await session.refresh(service)

    when = datetime.now(timezone.utc) + timedelta(minutes=minutes_until)

    booking = Booking(
        creator_id=creator.id,
        service_id=service.id,
        mechanic_id=mechanic.id,
        car_brand="Toyota",
        car_model="Corolla",
        car_number="WA12345",
        client_name="Jan Kowalski",
        client_phone="+48123456789",
        description_pl="Stuk w silniku",
        description_ru="Стук в двигателе",
        original_language="pl",
        booking_date=when,
        status=BookingStatus.ACCEPTED,
    )
    session.add(booking)
    await session.commit()
    await session.refresh(booking)

    return booking, mechanic


class TestReminderDeliveryTracking:
    async def test_successful_delivery_marks_sent(self, scheduler_session, monkeypatch):
        booking, _mechanic = await make_due_booking(scheduler_session)

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        scheduler = ReminderScheduler(mock_bot)

        await scheduler._process_cycle()

        await scheduler_session.refresh(booking)
        refreshed = booking
        assert refreshed.reminder_1h_sent is True
        mock_bot.send_message.assert_awaited_once()

    async def test_transient_failure_does_not_mark_sent(self, scheduler_session, monkeypatch):
        booking, _mechanic = await make_due_booking(scheduler_session)

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(side_effect=TimeoutError("network blip"))
        scheduler = ReminderScheduler(mock_bot)

        await scheduler._process_cycle()

        await scheduler_session.refresh(booking)
        refreshed = booking
        assert refreshed.reminder_1h_sent is False

    async def test_permanent_failure_marks_sent_to_stop_retrying(self, scheduler_session, monkeypatch):
        booking, _mechanic = await make_due_booking(scheduler_session)

        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(
            side_effect=TelegramForbiddenError(method=None, message="bot was blocked by the user")
        )
        scheduler = ReminderScheduler(mock_bot)

        await scheduler._process_cycle()

        await scheduler_session.refresh(booking)
        refreshed = booking
        assert refreshed.reminder_1h_sent is True
