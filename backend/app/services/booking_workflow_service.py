"""Booking Workflow Service - Facade over BookingService + NotificationService.

Multi-step booking scenarios (create, negotiate time, accept/reject) need
BookingService (state transitions) and NotificationService (who to tell about
it) to run together in a fixed sequence. Before this facade existed, that
sequencing lived in the handlers themselves (app/bot/handlers/booking.py,
mechanic.py), which is why the same ~15-line "call service, then notify"
dance was duplicated across several handler functions - see
docs/SOLID_DRY_FACADE_REFACTORING_PLAN.md, item 3.2.
"""

from datetime import datetime
from typing import Optional, Tuple

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService


class BookingWorkflowService:
    """Facade coordinating BookingService state transitions with the
    corresponding NotificationService calls, so callers don't have to
    remember which notification follows which state change."""

    def __init__(self, session: AsyncSession, bot: Optional[Bot]):
        self.session = session
        self.bot = bot
        self.booking_service = BookingService(session)
        self.notification_service = NotificationService(session, bot) if bot else None

    async def create_booking_and_notify(
        self,
        *,
        creator_telegram_id: int,
        service_id: int,
        car_brand: str,
        car_model: str,
        car_number: str,
        client_name: str,
        client_phone: str,
        description: str,
        language: str,
        booking_datetime: datetime,
    ) -> Tuple[Optional[Booking], str]:
        """Create a booking and, on success, notify every mechanic about it."""
        booking, msg = await self.booking_service.create_booking(
            creator_telegram_id=creator_telegram_id,
            service_id=service_id,
            car_brand=car_brand,
            car_model=car_model,
            car_number=car_number,
            client_name=client_name,
            client_phone=client_phone,
            description=description,
            language=language,
            booking_datetime=booking_datetime,
        )
        if booking and self.notification_service:
            await self.notification_service.notify_mechanics_new_booking(booking)
        return booking, msg

    async def propose_time_and_notify(
        self,
        *,
        booking_id: int,
        proposer_telegram_id: int,
        is_mechanic: bool,
        new_datetime: datetime,
    ) -> Tuple[Optional[Booking], str]:
        """Propose a new booking time (by mechanic or by creator) and notify
        the other party."""
        if is_mechanic:
            booking, msg = await self.booking_service.propose_new_time(
                booking_id, proposer_telegram_id, new_datetime
            )
            if booking and self.notification_service:
                proposer = await self.booking_service.user_repo.get_by_telegram_id(proposer_telegram_id)
                if proposer:
                    await self.notification_service.notify_time_change_proposed(booking, proposer)
        else:
            booking, msg = await self.booking_service.propose_new_time_by_user(
                booking_id, proposer_telegram_id, new_datetime
            )
            if booking and booking.mechanic and self.notification_service:
                proposer = await self.booking_service.user_repo.get_by_telegram_id(proposer_telegram_id)
                if proposer:
                    await self.notification_service.notify_user_time_change_proposed(booking, proposer)
        return booking, msg

    async def confirm_time_and_notify(
        self,
        *,
        booking_id: int,
        creator_telegram_id: int,
    ) -> Tuple[Optional[Booking], str]:
        """Confirm the mechanic-proposed time and notify the mechanic."""
        booking, msg = await self.booking_service.confirm_proposed_time(booking_id, creator_telegram_id)
        if booking and booking.mechanic and self.notification_service:
            creator = await self.booking_service.user_repo.get_by_telegram_id(creator_telegram_id)
            if creator:
                await self.notification_service.notify_time_confirmed(booking, creator)
        return booking, msg

    async def accept_and_notify(
        self,
        *,
        booking_id: int,
        mechanic_telegram_id: int,
    ) -> Tuple[Optional[Booking], str]:
        """Accept a booking and notify the creator + other mechanics."""
        booking, msg = await self.booking_service.accept_booking(booking_id, mechanic_telegram_id)
        if booking and self.notification_service:
            mechanic = await self.booking_service.user_repo.get_by_telegram_id(mechanic_telegram_id)
            if mechanic:
                await self.notification_service.notify_booking_accepted(booking, mechanic)
        return booking, msg

    async def reject_and_notify(
        self,
        *,
        booking_id: int,
        mechanic_telegram_id: int,
    ) -> Tuple[Optional[Booking], str]:
        """Reject a booking and notify the creator + other mechanics."""
        booking, msg = await self.booking_service.reject_booking(booking_id, mechanic_telegram_id)
        if booking and self.notification_service:
            mechanic = await self.booking_service.user_repo.get_by_telegram_id(mechanic_telegram_id)
            if mechanic:
                await self.notification_service.notify_booking_rejected(booking, mechanic)
        return booking, msg

    async def cancel_booking_and_notify(
        self,
        *,
        booking_id: int,
        actor_telegram_id: int,
    ) -> Tuple[Optional[Booking], str]:
        """Cancel a booking (creator/assigned mechanic/admin) and notify
        whichever party isn't the one who cancelled it."""
        booking, msg = await self.booking_service.cancel_booking(booking_id, actor_telegram_id)
        if booking and self.notification_service:
            actor = await self.booking_service.user_repo.get_by_telegram_id(actor_telegram_id)
            if actor:
                await self.notification_service.notify_booking_cancelled(booking, actor)
        return booking, msg
