"""Tests for BookingWorkflowService, the facade introduced in item 3.2 of
docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md to stop handlers from manually
sequencing BookingService + NotificationService calls.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import get_notification_rate_limiter
from app.core.timezone_utils import get_local_timezone
from app.models.booking import BookingStatus
from app.models.service import Service
from app.models.user import User, UserRole
from app.services.booking_service import BookingService
from app.services.booking_workflow_service import BookingWorkflowService


@pytest.fixture
def tomorrow_10am() -> datetime:
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
    svc = Service(name_pl="Wymiana oleju", name_ru="Замена масла", duration_minutes=30, is_active=True)
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


@pytest.fixture(autouse=True)
async def reset_notification_rate_limiter():
    limiter = get_notification_rate_limiter()
    await limiter.reset()
    yield
    await limiter.reset()


@pytest.fixture(autouse=True)
def no_background_menu_scheduling(monkeypatch):
    """accept_and_notify/reject_and_notify go through NotificationService,
    which schedules a delayed 'return to main menu' message via
    asyncio.create_task(...). Replace it with a no-op so tests stay fast and
    deterministic instead of leaking real background tasks across tests that
    reuse the same telegram_id (see docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md,
    item 1.1, for where this is imported from)."""
    monkeypatch.setattr(
        "app.services.notification_service.schedule_main_menu_return",
        MagicMock(),
    )


@pytest.fixture
def bot() -> AsyncMock:
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    return mock_bot


async def make_booking(db_session, creator, service, when):
    booking_service = BookingService(db_session)
    booking, _ = await booking_service.create_booking(
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
    assert booking is not None
    return booking


class TestCreateBookingAndNotify:
    async def test_creates_booking_and_notifies_mechanics(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        workflow = BookingWorkflowService(db_session, bot)

        booking, msg = await workflow.create_booking_and_notify(
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

        assert booking is not None
        assert booking.status == BookingStatus.PENDING
        assert msg == "Booking created successfully"
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id

    async def test_no_notification_sent_on_failure(self, db_session, creator, service, tomorrow_10am, bot):
        workflow = BookingWorkflowService(db_session, bot)

        booking, msg = await workflow.create_booking_and_notify(
            creator_telegram_id=999999,
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
        bot.send_message.assert_not_awaited()

    async def test_works_without_a_bot(self, db_session, creator, service, tomorrow_10am):
        """When no bot is available (e.g. background job), the facade still
        performs the state transition, it just skips notifications."""
        workflow = BookingWorkflowService(db_session, bot=None)

        booking, msg = await workflow.create_booking_and_notify(
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

        assert booking is not None
        assert msg == "Booking created successfully"


class TestAcceptRejectAndNotify:
    async def test_accept_notifies_creator(self, db_session, creator, mechanic, service, tomorrow_10am, bot):
        booking = await make_booking(db_session, creator, service, tomorrow_10am)
        workflow = BookingWorkflowService(db_session, bot)

        accepted, msg = await workflow.accept_and_notify(
            booking_id=booking.id, mechanic_telegram_id=mechanic.telegram_id
        )

        assert accepted is not None
        assert accepted.status == BookingStatus.ACCEPTED
        assert msg == "Booking accepted"
        notified_chat_ids = [call.args[0] for call in bot.send_message.await_args_list]
        assert creator.telegram_id in notified_chat_ids

    async def test_reject_notifies_creator(self, db_session, creator, mechanic, service, tomorrow_10am, bot):
        booking = await make_booking(db_session, creator, service, tomorrow_10am)
        workflow = BookingWorkflowService(db_session, bot)

        rejected, msg = await workflow.reject_and_notify(
            booking_id=booking.id, mechanic_telegram_id=mechanic.telegram_id
        )

        assert rejected is not None
        assert rejected.status == BookingStatus.REJECTED
        assert msg == "Booking rejected"
        notified_chat_ids = [call.args[0] for call in bot.send_message.await_args_list]
        assert creator.telegram_id in notified_chat_ids


class TestProposeAndConfirmTimeAndNotify:
    async def test_mechanic_proposal_notifies_creator(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking = await make_booking(db_session, creator, service, tomorrow_10am)
        workflow = BookingWorkflowService(db_session, bot)
        new_time = tomorrow_10am + timedelta(hours=2)

        proposed, msg = await workflow.propose_time_and_notify(
            booking_id=booking.id,
            proposer_telegram_id=mechanic.telegram_id,
            is_mechanic=True,
            new_datetime=new_time,
        )

        assert proposed is not None
        assert proposed.status == BookingStatus.NEGOTIATING
        assert msg == "New time proposed"
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == creator.telegram_id

    async def test_creator_proposal_notifies_mechanic(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking = await make_booking(db_session, creator, service, tomorrow_10am)
        workflow = BookingWorkflowService(db_session, bot)
        await workflow.accept_and_notify(booking_id=booking.id, mechanic_telegram_id=mechanic.telegram_id)
        bot.send_message.reset_mock()
        new_time = tomorrow_10am + timedelta(hours=2)

        proposed, msg = await workflow.propose_time_and_notify(
            booking_id=booking.id,
            proposer_telegram_id=creator.telegram_id,
            is_mechanic=False,
            new_datetime=new_time,
        )

        assert proposed is not None
        assert proposed.status == BookingStatus.NEGOTIATING
        assert msg == "New time proposed by user"
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id

    async def test_confirm_notifies_mechanic(self, db_session, creator, mechanic, service, tomorrow_10am, bot):
        booking = await make_booking(db_session, creator, service, tomorrow_10am)
        workflow = BookingWorkflowService(db_session, bot)
        new_time = tomorrow_10am + timedelta(hours=2)
        await workflow.propose_time_and_notify(
            booking_id=booking.id,
            proposer_telegram_id=mechanic.telegram_id,
            is_mechanic=True,
            new_datetime=new_time,
        )
        bot.send_message.reset_mock()

        confirmed, msg = await workflow.confirm_time_and_notify(
            booking_id=booking.id, creator_telegram_id=creator.telegram_id
        )

        assert confirmed is not None
        assert confirmed.status == BookingStatus.ACCEPTED
        assert msg == "Time confirmed"
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id
