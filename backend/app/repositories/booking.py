"""Booking repository"""

from typing import List, Optional
from datetime import datetime, date
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from .base import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    """Repository for Booking model"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Booking, session)
    
    async def get_with_relations(self, booking_id: int) -> Optional[Booking]:
        """
        Get booking with all relations loaded
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Booking with relations or None
        """
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.creator),
                selectinload(Booking.mechanic),
                selectinload(Booking.service)
            )
            .where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_date(self, target_date: date) -> List[Booking]:
        """
        Get all bookings for a specific date
        
        Args:
            target_date: Target date
            
        Returns:
            List of bookings
        """
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.service),
                selectinload(Booking.mechanic)
            )
            .where(
                and_(
                    Booking.booking_date >= start_datetime,
                    Booking.booking_date <= end_datetime,
                    Booking.status.in_([BookingStatus.ACCEPTED, BookingStatus.NEGOTIATING, BookingStatus.PENDING])
                )
            )
            .order_by(Booking.booking_date)
        )
        return list(result.scalars().all())
    
    async def get_pending_bookings(self) -> List[Booking]:
        """
        Get all pending bookings
        
        Returns:
            List of pending bookings
        """
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.creator),
                selectinload(Booking.service)
            )
            .where(Booking.status == BookingStatus.PENDING)
            .order_by(Booking.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_creator(self, creator_id: int, limit: int = 50) -> List[Booking]:
        """
        Get bookings created by specific user
        
        Args:
            creator_id: Creator user ID
            limit: Maximum number of bookings
            
        Returns:
            List of bookings
        """
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.service),
                selectinload(Booking.mechanic)
            )
            .where(Booking.creator_id == creator_id)
            .order_by(Booking.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_mechanic(self, mechanic_id: int, limit: int = 50) -> List[Booking]:
        """
        Get bookings assigned to specific mechanic
        
        Args:
            mechanic_id: Mechanic user ID
            limit: Maximum number of bookings
            
        Returns:
            List of bookings
        """
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.creator),
                selectinload(Booking.service)
            )
            .where(Booking.mechanic_id == mechanic_id)
            .order_by(Booking.booking_date)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def create_booking(
        self,
        creator_id: int,
        service_id: int,
        car_brand: str,
        car_model: str,
        car_number: str,
        client_name: str,
        client_phone: str,
        description_pl: str,
        description_ru: str,
        original_language: str,
        booking_date: datetime
    ) -> Booking:
        """
        Create new booking
        
        Args:
            creator_id: Creator user ID
            service_id: Service ID
            car_brand: Car brand
            car_model: Car model
            car_number: Car registration number
            client_name: Client name
            client_phone: Client phone
            description_pl: Description in Polish
            description_ru: Description in Russian
            original_language: Original language of description
            booking_date: Booking date and time
            
        Returns:
            Created booking
        """
        return await self.create(
            creator_id=creator_id,
            service_id=service_id,
            car_brand=car_brand,
            car_model=car_model,
            car_number=car_number,
            client_name=client_name,
            client_phone=client_phone,
            description_pl=description_pl,
            description_ru=description_ru,
            original_language=original_language,
            booking_date=booking_date,
            status=BookingStatus.PENDING
        )
    
    async def accept_booking(self, booking_id: int, mechanic_id: int) -> Optional[Booking]:
        """
        Accept booking by mechanic
        
        Args:
            booking_id: Booking ID
            mechanic_id: Mechanic user ID
            
        Returns:
            Updated booking or None
        """
        booking = await self.get_by_id(booking_id)
        if booking:
            booking.status = BookingStatus.ACCEPTED
            booking.mechanic_id = mechanic_id
            await self.session.flush()
            await self.session.refresh(booking)
        return booking
    
    async def reject_booking(self, booking_id: int) -> Optional[Booking]:
        """
        Reject booking
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Updated booking or None
        """
        booking = await self.get_by_id(booking_id)
        if booking:
            booking.status = BookingStatus.REJECTED
            await self.session.flush()
            await self.session.refresh(booking)
        return booking
    
    async def update_status(self, booking_id: int, status: BookingStatus) -> Optional[Booking]:
        """
        Update booking status
        
        Args:
            booking_id: Booking ID
            status: New status
            
        Returns:
            Updated booking or None
        """
        booking = await self.get_by_id(booking_id)
        if booking:
            booking.status = status
            await self.session.flush()
            await self.session.refresh(booking)
        return booking
    
    async def propose_new_time(
        self,
        booking_id: int,
        proposed_date: datetime,
        mechanic_id: int
    ) -> Optional[Booking]:
        """
        Propose new time for booking
        
        Args:
            booking_id: Booking ID
            proposed_date: Proposed date and time
            mechanic_id: Mechanic user ID
            
        Returns:
            Updated booking or None
        """
        booking = await self.get_by_id(booking_id)
        if booking:
            booking.proposed_date = proposed_date
            booking.mechanic_id = mechanic_id
            booking.status = BookingStatus.NEGOTIATING
            await self.session.flush()
            await self.session.refresh(booking)
        return booking
    
    async def confirm_proposed_time(self, booking_id: int) -> Optional[Booking]:
        """
        Confirm proposed time
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Updated booking or None
        """
        booking = await self.get_by_id(booking_id)
        if booking and booking.proposed_date:
            booking.booking_date = booking.proposed_date
            booking.proposed_date = None
            booking.status = BookingStatus.ACCEPTED
            await self.session.flush()
            await self.session.refresh(booking)
        return booking

