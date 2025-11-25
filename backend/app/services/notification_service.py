"""Notification Service - Handles sending notifications to users"""

from typing import List
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.user import User
from app.repositories.user import UserRepository
from app.core.i18n import get_text
from app.core.rate_limiter import get_notification_rate_limiter
from app.core.logging_config import get_logger
from .time_service import TimeService

logger = get_logger(__name__)


class NotificationService:
    """Service for sending notifications (SRP - Single Responsibility)"""
    
    def __init__(self, session: AsyncSession, bot: Bot):
        """
        Initialize notification service
        
        Args:
            session: Database session
            bot: Bot instance
        """
        self.session = session
        self.bot = bot
        self.user_repo = UserRepository(session)
        self.time_service = TimeService(session)
        self.rate_limiter = get_notification_rate_limiter()
    
    async def notify_mechanics_new_booking(self, booking: Booking) -> None:
        """
        Notify all mechanics about new booking
        
        Args:
            booking: Booking instance
        """
        mechanics = await self.user_repo.get_all_mechanics()
        
        for mechanic in mechanics:
            # Check rate limit before sending
            if await self.rate_limiter.is_allowed(mechanic.telegram_id):
                await self._send_new_booking_notification(mechanic, booking)
                await self.rate_limiter.record_message(mechanic.telegram_id)
            else:
                logger.warning(
                    f"Rate limit exceeded for mechanic {mechanic.telegram_id}, "
                    f"skipping new booking notification"
                )
    
    async def notify_booking_accepted(self, booking: Booking, mechanic: User) -> None:
        """
        Notify creator and other mechanics that booking was accepted
        
        Args:
            booking: Booking instance
            mechanic: Mechanic who accepted
        """
        # Notify creator
        await self._send_booking_accepted_notification(
            booking.creator,
            booking,
            mechanic
        )
        
        # Notify other mechanics
        mechanics = await self.user_repo.get_all_mechanics()
        for other_mechanic in mechanics:
            if other_mechanic.telegram_id != mechanic.telegram_id:
                await self._send_booking_accepted_notification(
                    other_mechanic,
                    booking,
                    mechanic
                )
    
    async def notify_booking_rejected(self, booking: Booking, mechanic: User) -> None:
        """
        Notify creator and other mechanics that booking was rejected
        
        Args:
            booking: Booking instance
            mechanic: Mechanic who rejected
        """
        # Notify creator
        await self._send_booking_rejected_notification(
            booking.creator,
            booking,
            mechanic
        )
        
        # Notify other mechanics
        mechanics = await self.user_repo.get_all_mechanics()
        for other_mechanic in mechanics:
            if other_mechanic.telegram_id != mechanic.telegram_id:
                await self._send_booking_rejected_notification(
                    other_mechanic,
                    booking,
                    mechanic
                )
    
    async def notify_time_change_proposed(
        self,
        booking: Booking,
        mechanic: User
    ) -> None:
        """
        Notify creator that mechanic proposed new time
        
        Args:
            booking: Booking instance
            mechanic: Mechanic who proposed new time
        """
        await self._send_time_change_notification(
            booking.creator,
            booking,
            mechanic
        )
    
    async def _send_new_booking_notification(
        self,
        user: User,
        booking: Booking
    ) -> None:
        """Send new booking notification to user"""
        lang = user.language
        
        notification = get_text("booking.notification.new_booking", lang).format(
            user_name=booking.creator.full_name,
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=self.time_service.format_date(booking.booking_date.date(), lang),
            time=self.time_service.format_time(booking.booking_date),
            description=booking.get_description(lang)
        )
        
        try:
            from app.bot.keyboards.inline import get_booking_actions_keyboard
            
            def _(key: str, **kwargs) -> str:
                return get_text(key, lang, **kwargs)
            
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(user.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for user {user.telegram_id}, "
                    f"skipping new booking notification"
                )
                return
            
            await self.bot.send_message(
                user.telegram_id,
                notification,
                reply_markup=get_booking_actions_keyboard(booking.id, _)
            )
            await self.rate_limiter.record_message(user.telegram_id)
        except Exception as e:
            logger.error(f"Failed to notify user {user.telegram_id}: {e}")

    async def notify_mechanic_reminder(
        self,
        booking: Booking,
        mechanic: User,
        time_label_key: str
    ) -> None:
        """Send reminder notification to assigned mechanic"""
        lang = mechanic.language
        time_left = get_text(time_label_key, lang)
        
        details_text = get_text("booking.confirm.details", lang).format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=self.time_service.format_date(booking.booking_date.date(), lang),
            time=self.time_service.format_time(booking.booking_date),
            description=booking.get_description(lang)
        )
        
        notification = get_text("booking.notification.reminder", lang).format(
            time_left=time_left,
            details=details_text
        )
        
        try:
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(mechanic.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for mechanic {mechanic.telegram_id}, "
                    f"skipping reminder notification"
                )
                return
            
            await self.bot.send_message(mechanic.telegram_id, notification)
            await self.rate_limiter.record_message(mechanic.telegram_id)
        except Exception as e:
            logger.error(f"Failed to send reminder to mechanic {mechanic.telegram_id}: {e}")
    
    async def _send_booking_accepted_notification(
        self,
        user: User,
        booking: Booking,
        mechanic: User
    ) -> None:
        """Send booking accepted notification"""
        lang = user.language
        
        details_text = get_text("booking.confirm.details", lang).format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=self.time_service.format_date(booking.booking_date.date(), lang),
            time=self.time_service.format_time(booking.booking_date),
            description=booking.get_description(lang)
        )
        
        notification = get_text("booking.notification.accepted", lang).format(
            mechanic_name=mechanic.full_name,
            details=details_text
        )
        
        try:
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(user.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for user {user.telegram_id}, "
                    f"skipping notification"
                )
                return
            
            await self.bot.send_message(user.telegram_id, notification)
            await self.rate_limiter.record_message(user.telegram_id)
        except Exception as e:
            logger.error(f"Failed to notify user {user.telegram_id}: {e}")
    
    async def _send_booking_rejected_notification(
        self,
        user: User,
        booking: Booking,
        mechanic: User
    ) -> None:
        """Send booking rejected notification"""
        lang = user.language
        
        details_text = get_text("booking.confirm.details", lang).format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=self.time_service.format_date(booking.booking_date.date(), lang),
            time=self.time_service.format_time(booking.booking_date),
            description=booking.get_description(lang)
        )
        
        notification = get_text("booking.notification.rejected", lang).format(
            mechanic_name=mechanic.full_name,
            details=details_text
        )
        
        try:
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(user.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for user {user.telegram_id}, "
                    f"skipping notification"
                )
                return
            
            await self.bot.send_message(user.telegram_id, notification)
            await self.rate_limiter.record_message(user.telegram_id)
        except Exception as e:
            logger.error(f"Failed to notify user {user.telegram_id}: {e}")
    
    async def _send_time_change_notification(
        self,
        user: User,
        booking: Booking,
        mechanic: User
    ) -> None:
        """Send time change notification"""
        lang = user.language
        
        if not booking.proposed_date:
            return
        
        details_text = get_text("booking.confirm.details", lang).format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=self.time_service.format_date(booking.proposed_date.date(), lang),
            time=self.time_service.format_time(booking.proposed_date),
            description=booking.get_description(lang)
        )
        
        notification = get_text("booking.notification.time_change", lang).format(
            mechanic_name=mechanic.full_name,
            date=self.time_service.format_date(booking.proposed_date.date(), lang),
            time=self.time_service.format_time(booking.proposed_date),
            details=details_text
        )
        
        try:
            from app.bot.keyboards.inline import get_confirmation_keyboard
            
            def _(key: str, **kwargs) -> str:
                return get_text(key, lang, **kwargs)
            
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(user.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for user {user.telegram_id}, "
                    f"skipping time change notification"
                )
                return
            
            await self.bot.send_message(
                user.telegram_id,
                notification,
                reply_markup=get_confirmation_keyboard(booking.id, _, show_change_time=True)
            )
            await self.rate_limiter.record_message(user.telegram_id)
        except Exception as e:
            logger.error(f"Failed to notify user {user.telegram_id}: {e}")

