"""Regression tests for item 2.1 in docs/REFACTORING_PLAN_2026-07.md (DIP):
BookingService and TimeService used to always construct their own concrete
repositories from `session`, making it impossible to unit test them without
a real (or real-shaped) AsyncSession/database. Both now accept their
repositories as optional constructor parameters.

These tests deliberately do NOT use the db_session fixture / a real
database - that's the point: proving the services are unit-testable with
plain fakes.
"""

from datetime import time
from unittest.mock import AsyncMock, MagicMock

from app.models.booking import Booking, BookingStatus
from app.models.settings import SystemSettings
from app.services.booking_service import BookingService
from app.services.time_service import TimeService


class TestBookingServiceAcceptsInjectedRepositories:
    async def test_uses_injected_booking_repo_without_a_real_session(self):
        fake_booking = Booking(id=1, status=BookingStatus.PENDING)
        fake_booking_repo = MagicMock()
        fake_booking_repo.get_pending_bookings = AsyncMock(return_value=[fake_booking])

        service = BookingService(
            session=MagicMock(),  # never touched by this call - proves booking_repo is what's used
            booking_repo=fake_booking_repo,
        )

        result = await service.get_pending_bookings()

        assert result == [fake_booking]
        fake_booking_repo.get_pending_bookings.assert_awaited_once()

    async def test_defaults_to_real_repositories_when_not_injected(self):
        """Backward compatibility: existing call sites do BookingService(session)
        with no other args and must keep working exactly as before."""
        from app.repositories.booking import BookingRepository
        from app.repositories.service import ServiceRepository
        from app.repositories.user import UserRepository

        service = BookingService(session=MagicMock())

        assert isinstance(service.booking_repo, BookingRepository)
        assert isinstance(service.service_repo, ServiceRepository)
        assert isinstance(service.user_repo, UserRepository)
        assert isinstance(service.time_service, TimeService)


class TestTimeServiceAcceptsInjectedRepositories:
    async def test_uses_injected_settings_repo_without_a_real_session(self):
        fake_settings = SystemSettings(
            work_start_time=time(8, 0),
            work_end_time=time(16, 0),
            time_step_minutes=15,
            buffer_time_minutes=10,
            timezone="Europe/Warsaw",
            booking_days_ahead=14,
        )
        fake_settings_repo = MagicMock()
        fake_settings_repo.get_settings = AsyncMock(return_value=fake_settings)

        service = TimeService(
            session=MagicMock(),
            settings_repo=fake_settings_repo,
        )

        step = await service.get_time_step()

        assert step == 15
        fake_settings_repo.get_settings.assert_awaited_once()

    async def test_defaults_to_real_repositories_when_not_injected(self):
        from app.repositories.booking import BookingRepository
        from app.repositories.settings import SettingsRepository

        service = TimeService(session=MagicMock())

        assert isinstance(service.booking_repo, BookingRepository)
        assert isinstance(service.settings_repo, SettingsRepository)
