"""Booking Service - Business logic for bookings"""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.service import Service
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.service import ServiceRepository
from app.repositories.user import UserRepository
from app.core.timezone_utils import ensure_utc, ensure_local
from app.core.logging_config import get_logger
from .translation_service import translate_to_all_languages
from .time_service import TimeService


logger = get_logger(__name__)


class BookingService:
    """Service for handling booking operations (SRP)"""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize booking service
        
        Args:
            session: Database session
        """
        self.session = session
        self.booking_repo = BookingRepository(session)
        self.service_repo = ServiceRepository(session)
        self.user_repo = UserRepository(session)
        self.time_service = TimeService(session)
    
    async def create_booking(
        self,
        creator_telegram_id: int,
        service_id: int,
        car_brand: str,
        car_model: str,
        car_number: str,
        client_name: str,
        client_phone: str,
        description: str,
        language: str,
        booking_datetime: datetime
    ) -> Tuple[Optional[Booking], str]:
        """
        Create new booking
        
        Args:
            creator_telegram_id: Creator's Telegram ID
            service_id: Service ID
            car_brand: Car brand
            car_model: Car model
            car_number: Car registration number
            client_name: Client name
            client_phone: Client phone
            description: Problem description
            language: Original language of description
            booking_datetime: Booking date and time
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Get creator
        creator = await self.user_repo.get_by_telegram_id(creator_telegram_id)
        if not creator:
            return None, "Creator not found"
        
        # Get service
        service = await self.service_repo.get_by_id(service_id)
        if not service or not service.is_active:
            return None, "Service not found or inactive"
        
        # Ensure booking_datetime is timezone-aware and in local timezone
        # Store time in local timezone (not UTC) as requested
        booking_datetime_local = ensure_local(booking_datetime)
        
        # Log booking creation for debugging
        logger.info(
            "Creating booking with datetime",
            original_datetime=str(booking_datetime),
            original_tzinfo=str(booking_datetime.tzinfo) if booking_datetime.tzinfo else "None",
            original_minute=booking_datetime.minute if booking_datetime.tzinfo else None,
            local_datetime=str(booking_datetime_local),
            local_hour=booking_datetime_local.hour,
            local_minute=booking_datetime_local.minute
        )
        
        # Check if time slot is available (use local timezone)
        is_available = await self.time_service.is_slot_available(
            booking_datetime_local,
            service.duration_minutes
        )
        
        if not is_available:
            return None, "Time slot is not available"
        
        # Translate description to all languages
        translations = await translate_to_all_languages(
            description,
            source_lang=language,
        )
        
        # Create booking (store in local timezone as requested)
        booking = await self.booking_repo.create_booking(
            creator_id=creator.id,
            service_id=service_id,
            car_brand=car_brand,
            car_model=car_model,
            car_number=car_number,
            client_name=client_name,
            client_phone=client_phone,
            description_pl=translations["pl"],
            description_ru=translations["ru"],
            original_language=language,
            booking_date=booking_datetime_local
        )
        
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking.id)
        
        # Log for debugging (can be removed later)
        if booking:
            logger.info(
                "Booking created - reading back from DB",
                booking_id=booking.id,
                booking_date_from_db=str(booking.booking_date),
                booking_date_tzinfo=str(booking.booking_date.tzinfo) if booking.booking_date.tzinfo else "None",
                booking_date_hour=booking.booking_date.hour,
                booking_date_minute=booking.booking_date.minute
            )
        
        return booking, "Booking created successfully"
    
    async def get_pending_bookings(self) -> List[Booking]:
        """
        Get all pending bookings
        
        Returns:
            List of pending bookings
        """
        return await self.booking_repo.get_pending_bookings()
    
    async def get_user_bookings(self, telegram_id: int) -> List[Booking]:
        """
        Get user's bookings
        
        Args:
            telegram_id: User's Telegram ID
            
        Returns:
            List of bookings
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        
        return await self.booking_repo.get_by_creator(user.id)
    
    async def get_mechanic_bookings(self, telegram_id: int) -> List[Booking]:
        """
        Get mechanic's assigned bookings
        
        Args:
            telegram_id: Mechanic's Telegram ID
            
        Returns:
            List of bookings
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        
        return await self.booking_repo.get_by_mechanic(user.id)
    
    async def accept_booking(
        self,
        booking_id: int,
        mechanic_telegram_id: int
    ) -> Tuple[Optional[Booking], str]:
        """
        Accept booking by mechanic
        
        Args:
            booking_id: Booking ID
            mechanic_telegram_id: Mechanic's Telegram ID
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Get mechanic
        mechanic = await self.user_repo.get_by_telegram_id(mechanic_telegram_id)
        if not mechanic:
            return None, "Mechanic not found"
        
        # Get booking
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            return None, "Booking not found"
        
        if booking.status != BookingStatus.PENDING:
            return None, "Booking is not in pending status"
        
        # Accept booking
        booking = await self.booking_repo.accept_booking(booking_id, mechanic.id)
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking_id)
        
        return booking, "Booking accepted"
    
    async def reject_booking(
        self,
        booking_id: int,
        mechanic_telegram_id: int
    ) -> Tuple[Optional[Booking], str]:
        """
        Reject booking by mechanic
        
        Args:
            booking_id: Booking ID
            mechanic_telegram_id: Mechanic's Telegram ID
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Verify mechanic exists
        mechanic = await self.user_repo.get_by_telegram_id(mechanic_telegram_id)
        if not mechanic:
            return None, "Mechanic not found"
        
        # Get booking
        booking = await self.booking_repo.get_by_id(booking_id)
        if not booking:
            return None, "Booking not found"
        
        if booking.status != BookingStatus.PENDING:
            return None, "Booking is not in pending status"
        
        # Reject booking
        booking = await self.booking_repo.reject_booking(booking_id)
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking_id)
        
        return booking, "Booking rejected"
    
    async def propose_new_time(
        self,
        booking_id: int,
        mechanic_telegram_id: int,
        new_datetime: datetime
    ) -> Tuple[Optional[Booking], str]:
        """
        Propose new time for booking
        
        Args:
            booking_id: Booking ID
            mechanic_telegram_id: Mechanic's Telegram ID
            new_datetime: Proposed new date and time
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Get mechanic
        mechanic = await self.user_repo.get_by_telegram_id(mechanic_telegram_id)
        if not mechanic:
            return None, "Mechanic not found"
        
        # Get booking
        booking = await self.booking_repo.get_with_relations(booking_id)
        if not booking:
            return None, "Booking not found"
        
        # Ensure new_datetime is in local timezone
        new_datetime_local = ensure_local(new_datetime)
        
        # Check if new time slot is available (use local timezone)
        is_available = await self.time_service.is_slot_available(
            new_datetime_local,
            booking.service.duration_minutes,
            exclude_booking_id=booking_id
        )
        
        if not is_available:
            return None, "Proposed time slot is not available"
        
        # Propose new time (store in local timezone)
        booking = await self.booking_repo.propose_new_time(
            booking_id,
            new_datetime_local,
            mechanic.id
        )
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking_id)
        
        return booking, "New time proposed"
    
    async def propose_new_time_by_user(
        self,
        booking_id: int,
        creator_telegram_id: int,
        new_datetime: datetime
    ) -> Tuple[Optional[Booking], str]:
        """
        Propose new time for booking by user (creator)
        
        Args:
            booking_id: Booking ID
            creator_telegram_id: Creator's Telegram ID
            new_datetime: Proposed new date and time
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Get creator
        creator = await self.user_repo.get_by_telegram_id(creator_telegram_id)
        if not creator:
            return None, "User not found"
        
        # Get booking
        booking = await self.booking_repo.get_with_relations(booking_id)
        if not booking:
            return None, "Booking not found"
        
        # Verify creator
        if booking.creator_id != creator.id:
            return None, "Unauthorized"
        
        # Ensure new_datetime is in local timezone
        new_datetime_local = ensure_local(new_datetime)
        
        # Check if new time slot is available (use local timezone)
        is_available = await self.time_service.is_slot_available(
            new_datetime_local,
            booking.service.duration_minutes,
            exclude_booking_id=booking_id
        )
        
        if not is_available:
            return None, "Proposed time slot is not available"
        
        # Propose new time (set proposed_date, status to NEGOTIATING, store in local timezone)
        booking.proposed_date = new_datetime_local
        booking.status = BookingStatus.NEGOTIATING
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking_id)
        
        return booking, "New time proposed by user"
    
    async def confirm_proposed_time(
        self,
        booking_id: int,
        creator_telegram_id: int
    ) -> Tuple[Optional[Booking], str]:
        """
        Confirm proposed time by creator
        
        Args:
            booking_id: Booking ID
            creator_telegram_id: Creator's Telegram ID
            
        Returns:
            Tuple of (Booking, message) or (None, error_message)
        """
        # Get booking
        booking = await self.booking_repo.get_with_relations(booking_id)
        if not booking:
            return None, "Booking not found"
        
        # Verify creator
        creator = await self.user_repo.get_by_telegram_id(creator_telegram_id)
        if not creator or booking.creator_id != creator.id:
            return None, "Unauthorized"
        
        if booking.status != BookingStatus.NEGOTIATING:
            return None, "Booking is not in negotiating status"
        
        if not booking.proposed_date:
            return None, "No proposed time found"
        
        # Confirm proposed time
        booking = await self.booking_repo.confirm_proposed_time(booking_id)
        await self.session.commit()
        
        # Load relations
        booking = await self.booking_repo.get_with_relations(booking_id)
        
        return booking, "Time confirmed"
    
    async def get_booking_details(self, booking_id: int) -> Optional[Booking]:
        """
        Get booking with all details
        
        Args:
            booking_id: Booking ID
            
        Returns:
            Booking with relations or None
        """
        return await self.booking_repo.get_with_relations(booking_id)
    
    async def cancel_booking(
        self,
        booking_id: int,
        user_telegram_id: int
    ) -> Tuple[bool, str]:
        """
        Cancel booking
        
        Args:
            booking_id: Booking ID
            user_telegram_id: User's Telegram ID
            
        Returns:
            Tuple of (success, message)
        """
        # Get booking
        booking = await self.booking_repo.get_with_relations(booking_id)
        if not booking:
            return False, "Booking not found"
        
        # Verify user is creator
        user = await self.user_repo.get_by_telegram_id(user_telegram_id)
        if not user or booking.creator_id != user.id:
            return False, "Unauthorized"
        
        # Update status to cancelled
        await self.booking_repo.update_status(booking_id, BookingStatus.CANCELLED)
        await self.session.commit()
        
        return True, "Booking cancelled"

