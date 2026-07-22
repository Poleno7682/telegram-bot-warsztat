"""Tests for the AuthService methods added while executing item 2.4 of
docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md (moving user listing/reminder
updates out of handlers, which used to call UserRepository directly).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService


@pytest.fixture
async def mechanic(db_session: AsyncSession) -> User:
    user = User(telegram_id=2002, first_name="Mechanic", role=UserRole.MECHANIC, is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def plain_user(db_session: AsyncSession) -> User:
    user = User(telegram_id=3003, first_name="Plain", role=UserRole.USER, is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestListing:
    async def test_get_all_mechanics_returns_only_mechanics(self, db_session, mechanic, plain_user):
        auth_service = AuthService(db_session)

        mechanics = await auth_service.get_all_mechanics()

        assert [m.telegram_id for m in mechanics] == [mechanic.telegram_id]

    async def test_get_all_users_returns_only_plain_users(self, db_session, mechanic, plain_user):
        auth_service = AuthService(db_session)

        users = await auth_service.get_all_users()

        assert [u.telegram_id for u in users] == [plain_user.telegram_id]


class TestUpdateReminderSettings:
    async def test_updates_only_the_given_field(self, db_session, mechanic):
        auth_service = AuthService(db_session)

        updated = await auth_service.update_reminder_settings(
            mechanic.telegram_id, reminder_1h_enabled=False
        )

        assert updated is not None
        assert updated.reminder_1h_enabled is False
        # Untouched fields keep their defaults
        assert updated.reminder_3h_enabled is True
        assert updated.reminder_30m_enabled is True

    async def test_returns_none_for_unknown_user(self, db_session):
        auth_service = AuthService(db_session)

        updated = await auth_service.update_reminder_settings(999999, reminder_1h_enabled=False)

        assert updated is None
