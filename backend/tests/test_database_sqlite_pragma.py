"""Regression tests for item 2.4.3 in docs/REFACTORING_PLAN_2026-07.md:
SQLite doesn't enforce foreign keys by default, so Booking's
ondelete=CASCADE/RESTRICT/SET NULL was silently a no-op under SQLite
(used in dev/tests; production uses PostgreSQL, where it worked correctly
all along) - an integrity bug there could go unnoticed until it hit prod.

Uses its own throwaway SQLite engine (not the app's real `engine`, which
in this environment is configured for a real PostgreSQL instance) but
exercises the exact same enable_sqlite_foreign_keys() helper the app uses.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import enable_sqlite_foreign_keys
from app.models.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.models.user import User, UserRole


async def make_engine(with_pragma: bool):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    if with_pragma:
        enable_sqlite_foreign_keys(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


class TestSqliteForeignKeyPragma:
    async def test_pragma_reports_enabled_when_applied(self):
        engine = await make_engine(with_pragma=True)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            assert result.scalar() == 1
        await engine.dispose()

    async def test_pragma_reports_disabled_without_the_fix(self):
        """Control case: proves the default SQLite behavior this fix
        changes - without enable_sqlite_foreign_keys, FKs are OFF."""
        engine = await make_engine(with_pragma=False)
        async with engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            assert result.scalar() == 0
        await engine.dispose()

    async def test_cascade_delete_enforced_with_pragma(self):
        """Booking.creator_id has ondelete=CASCADE at the DB level - a raw
        DELETE of the creator row must cascade-delete their bookings too,
        but only once FKs are enforced.

        Deletes via raw SQL rather than session.delete(creator): the ORM
        manages its own cascade behavior on top of (independently from)
        the DB-level ondelete, and would otherwise try to null out the
        NOT NULL creator_id itself before this pragma even comes into
        play. Raw SQL isolates what's actually being tested here - the
        database's own FK enforcement.
        """
        engine = await make_engine(with_pragma=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            creator = User(telegram_id=1, first_name="C", role=UserRole.USER)
            service = Service(name_pl="a", name_ru="b", duration_minutes=10)
            session.add_all([creator, service])
            await session.commit()

            booking = Booking(
                creator_id=creator.id,
                service_id=service.id,
                car_brand="Toyota",
                car_model="Corolla",
                car_number="X",
                client_name="Y",
                client_phone="Z",
                description_pl="d",
                description_ru="d",
                original_language="pl",
                booking_date=datetime.now(timezone.utc) + timedelta(days=1),
                status=BookingStatus.PENDING,
            )
            session.add(booking)
            await session.commit()
            booking_id = booking.id
            creator_id = creator.id

            await session.execute(text("DELETE FROM users_booking_bot WHERE id = :id"), {"id": creator_id})
            await session.commit()
            # The `booking` Python object is still sitting in the
            # session's identity map from the insert above - .get() would
            # return it straight from there without re-querying, masking
            # whether the row actually still exists in the DB.
            session.expire_all()

            remaining = await session.get(Booking, booking_id)
            assert remaining is None

        await engine.dispose()

    async def test_invalid_foreign_key_rejected_with_pragma(self):
        """With FKs enforced, inserting a booking that references a
        nonexistent service must fail instead of silently succeeding."""
        engine = await make_engine(with_pragma=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            creator = User(telegram_id=2, first_name="C", role=UserRole.USER)
            session.add(creator)
            await session.commit()

            booking = Booking(
                creator_id=creator.id,
                service_id=999999,  # does not exist
                car_brand="Toyota",
                car_model="Corolla",
                car_number="X",
                client_name="Y",
                client_phone="Z",
                description_pl="d",
                description_ru="d",
                original_language="pl",
                booking_date=datetime.now(timezone.utc) + timedelta(days=1),
                status=BookingStatus.PENDING,
            )
            session.add(booking)
            with pytest.raises(IntegrityError):
                await session.commit()

        await engine.dispose()
