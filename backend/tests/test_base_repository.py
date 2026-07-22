"""Tests for BaseRepository.get_all()/count() filtering (Phase 1, item 1.3
of docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md).

Exercised through UserRepository since BaseRepository is generic and not
meant to be instantiated directly.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.user import UserRepository


@pytest.fixture
async def seeded_users(db_session: AsyncSession) -> list[User]:
    users = [
        User(telegram_id=1, role=UserRole.ADMIN, is_active=True),
        User(telegram_id=2, role=UserRole.MECHANIC, is_active=True),
        User(telegram_id=3, role=UserRole.MECHANIC, is_active=True),
        User(telegram_id=4, role=UserRole.MECHANIC, is_active=False),
        User(telegram_id=5, role=UserRole.USER, is_active=True),
    ]
    db_session.add_all(users)
    await db_session.commit()
    return users


class TestGetAllAndCountAgree:
    async def test_count_matches_get_all_length_without_filters(self, db_session, seeded_users):
        repo = UserRepository(db_session)

        all_users = await repo.get_all(limit=100)
        total = await repo.count()

        assert total == len(all_users) == 5

    async def test_count_matches_get_all_length_with_single_filter(self, db_session, seeded_users):
        repo = UserRepository(db_session)

        mechanics = await repo.get_all(limit=100, role=UserRole.MECHANIC)
        mechanics_count = await repo.count(role=UserRole.MECHANIC)

        assert mechanics_count == len(mechanics) == 3

    async def test_count_matches_get_all_length_with_multiple_filters(self, db_session, seeded_users):
        repo = UserRepository(db_session)

        active_mechanics = await repo.get_all(limit=100, role=UserRole.MECHANIC, is_active=True)
        active_mechanics_count = await repo.count(role=UserRole.MECHANIC, is_active=True)

        assert active_mechanics_count == len(active_mechanics) == 2

    async def test_unknown_filter_key_is_ignored_not_erroring(self, db_session, seeded_users):
        repo = UserRepository(db_session)

        total = await repo.count(not_a_real_column="whatever")

        assert total == 5
