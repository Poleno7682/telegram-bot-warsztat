"""Regression test for item 2.4.4 in docs/REFACTORING_PLAN_2026-07.md:
Booking.service used to rely on every query site remembering to
selectinload(Booking.service) - a future query that forgot it would raise
MissingGreenlet under async SQLAlchemy the moment .service was accessed.
lazy="selectin" on the relationship makes eager loading the default.

Uses two separate sessions on the same throwaway engine (rather than the
shared db_session fixture) so the second, read-only session has no prior
identity-map knowledge of the booking - a clean test of what a fresh plain
query (no selectinload option at all) eager-loads by default.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.models.user import User, UserRole


async def test_booking_service_accessible_without_explicit_selectinload():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as write_session:
        creator = User(telegram_id=7001, first_name="C", role=UserRole.USER)
        service = Service(name_pl="Test", name_ru="Тест", duration_minutes=10)
        write_session.add_all([creator, service])
        await write_session.commit()

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
        write_session.add(booking)
        await write_session.commit()
        booking_id = booking.id

    # Fresh session, fresh identity map: a plain query with no
    # selectinload(Booking.service) at all - the scenario that used to
    # crash with MissingGreenlet on .service access.
    async with session_factory() as read_session:
        result = await read_session.execute(select(Booking).where(Booking.id == booking_id))
        fetched = result.scalar_one()

        assert fetched.service.name_pl == "Test"

    await engine.dispose()
