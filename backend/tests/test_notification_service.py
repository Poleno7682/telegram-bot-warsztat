"""Safety-net tests for NotificationService.

These tests exist to catch regressions while executing the refactoring plan
in docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md (Phase 0), in particular item
1.1 (moving menu-building out of the service layer) and 2.5 (deduplicating
the notification-sending templates). The Bot is mocked so no real Telegram
API calls are made.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import get_notification_rate_limiter
from app.core.timezone_utils import get_local_timezone
from app.models.service import Service
from app.models.user import User, UserRole
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService


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
async def other_mechanic(db_session: AsyncSession) -> User:
    user = User(telegram_id=3003, first_name="OtherMechanic", role=UserRole.MECHANIC, language="ru")
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
    """get_notification_rate_limiter() is a process-wide singleton keyed by
    telegram_id. Without a reset, tests reusing the same fixture telegram_id
    (e.g. mechanic=2002) trip each other's rate limit within the same 60s
    real-time window, causing order-dependent failures."""
    limiter = get_notification_rate_limiter()
    await limiter.reset()
    yield
    await limiter.reset()


@pytest.fixture(autouse=True)
def no_background_menu_scheduling(monkeypatch):
    """notify_booking_accepted/rejected schedule a delayed 'return to main menu'
    message via asyncio.create_task(...). Replace it with a no-op so tests stay
    fast and deterministic instead of racing a real background task.

    Patched where NotificationService actually looks it up: it imports
    schedule_main_menu_return directly from app.bot.ui.menu at module level
    (see docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md, item 1.1), so patching
    the app.bot.handlers.common re-export would not affect it.
    """
    monkeypatch.setattr(
        "app.services.notification_service.schedule_main_menu_return",
        MagicMock(),
    )


@pytest.fixture
def bot() -> AsyncMock:
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    return mock_bot


async def make_booking_with_relations(db_session, creator, service, when):
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


class TestNotifyMechanicsNewBooking:
    async def test_sends_to_every_mechanic(
        self, db_session, creator, mechanic, other_mechanic, service, tomorrow_10am, bot
    ):
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_mechanics_new_booking(booking)

        assert bot.send_message.await_count == 2
        notified_chat_ids = {call.args[0] for call in bot.send_message.await_args_list}
        assert notified_chat_ids == {mechanic.telegram_id, other_mechanic.telegram_id}

    async def test_skips_rate_limited_mechanic(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot, monkeypatch
    ):
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)
        monkeypatch.setattr(notification_service.rate_limiter, "is_allowed", AsyncMock(return_value=False))

        await notification_service.notify_mechanics_new_booking(booking)

        bot.send_message.assert_not_awaited()

    async def test_excludes_creator_when_creator_is_also_a_mechanic(
        self, db_session, mechanic, other_mechanic, service, tomorrow_10am, bot
    ):
        """A mechanic can create their own booking (bot/handlers/booking.py's
        custom-service flow, or the regular "new booking" menu option
        mechanics always had) - they must not get an accept/reject push
        for their own submission. Regression for a production bug: this
        self-notification, combined with self-accepting it, sent the
        mechanic's main menu twice."""
        booking = await make_booking_with_relations(db_session, mechanic, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_mechanics_new_booking(booking)

        notified_chat_ids = {call.args[0] for call in bot.send_message.await_args_list}
        assert mechanic.telegram_id not in notified_chat_ids
        assert other_mechanic.telegram_id in notified_chat_ids


class TestNotifyBookingAcceptedRejected:
    async def test_accepted_notifies_creator_and_other_mechanics_not_acceptor(
        self, db_session, creator, mechanic, other_mechanic, service, tomorrow_10am, bot
    ):
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_booking_accepted(booking, mechanic)

        notified_chat_ids = [call.args[0] for call in bot.send_message.await_args_list]
        # Creator gets the "accepted" notification, the acceptor gets a confirmation
        # message, and every other mechanic gets notified too - but not the acceptor twice.
        assert creator.telegram_id in notified_chat_ids
        assert mechanic.telegram_id in notified_chat_ids
        assert other_mechanic.telegram_id in notified_chat_ids
        assert notified_chat_ids.count(mechanic.telegram_id) == 1

    async def test_rejected_notifies_creator_and_other_mechanics(
        self, db_session, creator, mechanic, other_mechanic, service, tomorrow_10am, bot
    ):
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_booking_rejected(booking, mechanic)

        notified_chat_ids = [call.args[0] for call in bot.send_message.await_args_list]
        assert creator.telegram_id in notified_chat_ids
        assert other_mechanic.telegram_id in notified_chat_ids
        assert mechanic.telegram_id not in notified_chat_ids

    async def test_self_accept_sends_one_confirmation_and_skips_creator_menu_return(
        self, db_session, mechanic, other_mechanic, service, tomorrow_10am, bot, monkeypatch
    ):
        """Regression test for the production duplicate-menu bug: a
        mechanic accepting their own booking (e.g. from the pending list,
        or the self-notification the previous test now prevents) used to
        get both the creator-facing "accepted" notification + a
        3-second-delayed menu return, AND the mechanic-facing
        confirmation with an embedded menu - two "Panel mechanika"
        sends to the same chat.
        """
        schedule_mock = MagicMock()
        monkeypatch.setattr(
            "app.services.notification_service.schedule_main_menu_return", schedule_mock
        )
        booking = await make_booking_with_relations(db_session, mechanic, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_booking_accepted(booking, mechanic)

        notified_chat_ids = [call.args[0] for call in bot.send_message.await_args_list]
        assert notified_chat_ids.count(mechanic.telegram_id) == 1
        assert other_mechanic.telegram_id in notified_chat_ids
        # The creator-facing branch (redundant here - creator == acceptor)
        # must be skipped entirely, not just deduplicated after the fact.
        schedule_mock.assert_not_called()


class TestNotifyTimeNegotiation:
    async def test_notify_time_change_proposed_targets_creator(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        proposed, _ = await booking_service.propose_new_time(
            booking.id, mechanic.telegram_id, tomorrow_10am + timedelta(hours=2)
        )
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_time_change_proposed(proposed, mechanic)

        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == creator.telegram_id

    async def test_notify_user_time_change_proposed_targets_mechanic(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        await booking_service.accept_booking(booking.id, mechanic.telegram_id)
        proposed, _ = await booking_service.propose_new_time_by_user(
            booking.id, creator.telegram_id, tomorrow_10am + timedelta(hours=2)
        )
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_user_time_change_proposed(proposed, creator)

        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id

    async def test_notify_user_time_change_proposed_noop_without_mechanic(
        self, db_session, creator, service, tomorrow_10am, bot
    ):
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_user_time_change_proposed(booking, creator)

        bot.send_message.assert_not_awaited()

    async def test_notify_time_confirmed_targets_mechanic(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        await booking_service.propose_new_time(booking.id, mechanic.telegram_id, tomorrow_10am + timedelta(hours=2))
        confirmed, _ = await booking_service.confirm_proposed_time(booking.id, creator.telegram_id)
        notification_service = NotificationService(db_session, bot)

        await notification_service.notify_time_confirmed(confirmed, creator)

        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id


class TestNotifyMechanicReminder:
    async def test_sends_reminder_to_mechanic(self, db_session, creator, mechanic, service, tomorrow_10am, bot):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        accepted, _ = await booking_service.accept_booking(booking.id, mechanic.telegram_id)
        notification_service = NotificationService(db_session, bot)

        delivered = await notification_service.notify_mechanic_reminder(
            accepted, mechanic, "booking.reminder.time_left_1h"
        )

        assert delivered is True
        bot.send_message.assert_awaited_once()
        assert bot.send_message.await_args.args[0] == mechanic.telegram_id

    async def test_skips_reminder_when_rate_limited(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot, monkeypatch
    ):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        accepted, _ = await booking_service.accept_booking(booking.id, mechanic.telegram_id)
        notification_service = NotificationService(db_session, bot)
        monkeypatch.setattr(notification_service.rate_limiter, "is_allowed", AsyncMock(return_value=False))

        delivered = await notification_service.notify_mechanic_reminder(
            accepted, mechanic, "booking.reminder.time_left_1h"
        )

        assert delivered is False
        bot.send_message.assert_not_awaited()

    async def test_transient_send_failure_returns_false(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        accepted, _ = await booking_service.accept_booking(booking.id, mechanic.telegram_id)
        notification_service = NotificationService(db_session, bot)
        bot.send_message.side_effect = TimeoutError("network blip")

        delivered = await notification_service.notify_mechanic_reminder(
            accepted, mechanic, "booking.reminder.time_left_1h"
        )

        assert delivered is False

    async def test_forbidden_send_failure_returns_true(
        self, db_session, creator, mechanic, service, tomorrow_10am, bot
    ):
        from aiogram.exceptions import TelegramForbiddenError

        booking_service = BookingService(db_session)
        booking = await make_booking_with_relations(db_session, creator, service, tomorrow_10am)
        accepted, _ = await booking_service.accept_booking(booking.id, mechanic.telegram_id)
        notification_service = NotificationService(db_session, bot)
        bot.send_message.side_effect = TelegramForbiddenError(method=None, message="bot was blocked by the user")

        delivered = await notification_service.notify_mechanic_reminder(
            accepted, mechanic, "booking.reminder.time_left_1h"
        )

        assert delivered is True
