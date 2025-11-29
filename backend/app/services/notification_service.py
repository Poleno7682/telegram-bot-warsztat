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
from app.utils.date_formatter import DateFormatter
from app.utils.booking_utils import format_booking_details
from app.utils.user_utils import get_user_language

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
        
        # Return creator to main menu after 3 seconds
        from app.bot.handlers.common import schedule_main_menu_return
        schedule_main_menu_return(self.bot, booking.creator.telegram_id, booking.creator, delay=3.0)
        
        # Send confirmation message to mechanic with main menu
        from app.core.i18n import get_text
        from app.bot.handlers.common import _build_menu_payload
        from app.core.deferred_message_manager import get_deferred_message_manager
        
        # Cancel any scheduled menu return for mechanic to prevent duplicate
        manager = get_deferred_message_manager()
        await manager.cancel_message(mechanic.telegram_id)
        
        lang = get_user_language(mechanic)
        confirmation_text = get_text("booking.notification.accepted_mechanic", lang, default="✅ Запись принята")
        
        # Get main menu text and keyboard
        menu_text, keyboard = _build_menu_payload(mechanic)
        
        # Combine confirmation message with main menu
        full_message = f"{confirmation_text}\n\n{menu_text}"
        
        try:
            # Check rate limit before sending
            if await self.rate_limiter.is_allowed(mechanic.telegram_id):
                await self.bot.send_message(mechanic.telegram_id, full_message, reply_markup=keyboard)
                await self.rate_limiter.record_message(mechanic.telegram_id)
        except Exception as e:
            logger.error(f"Failed to send confirmation to mechanic {mechanic.telegram_id}: {e}")
        
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
        
        # Return creator to main menu after 3 seconds
        from app.bot.handlers.common import schedule_main_menu_return
        schedule_main_menu_return(self.bot, booking.creator.telegram_id, booking.creator, delay=3.0)
        
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
    
    async def notify_user_time_change_proposed(
        self,
        booking: Booking,
        user: User
    ) -> None:
        """
        Notify mechanic that user (creator) proposed new time
        
        Args:
            booking: Booking instance
            user: User (creator) who proposed new time
        """
        if not booking.mechanic:
            return
        
        await self._send_time_change_notification(
            booking.mechanic,
            booking,
            user
        )
    
    async def notify_time_confirmed(
        self,
        booking: Booking,
        user: User
    ) -> None:
        """
        Notify mechanic that user (creator) confirmed proposed time
        
        Args:
            booking: Booking instance
            user: User (creator) who confirmed the time
        """
        if not booking.mechanic:
            return
        
        await self._send_time_confirmed_notification(
            booking.mechanic,
            booking,
            user
        )
    
    async def _send_new_booking_notification(
        self,
        user: User,
        booking: Booking
    ) -> None:
        """Send new booking notification to user"""
        lang = get_user_language(user)
        
        notification = get_text("booking.notification.new_booking", lang).format(
            user_name=booking.creator.full_name,
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=DateFormatter.format_date(booking.booking_date, lang),
            time=DateFormatter.format_time(booking.booking_date),
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
        lang = get_user_language(mechanic)
        time_left = get_text(time_label_key, lang)
        
        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)
        
        details_text = format_booking_details(booking, lang, _)
        
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
        lang = get_user_language(user)
        
        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)
        
        details_text = format_booking_details(booking, lang, _)
        
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
        lang = get_user_language(user)
        
        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)
        
        details_text = format_booking_details(booking, lang, _)
        
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
    
    async def _send_time_confirmed_notification(
        self,
        mechanic: User,
        booking: Booking,
        user: User
    ) -> None:
        """Send time confirmed notification to mechanic"""
        lang = get_user_language(mechanic)
        
        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)
        
        details_text = format_booking_details(booking, lang, _)
        
        notification = get_text("booking.notification.time_confirmed", lang).format(
            user_name=user.full_name,
            date=DateFormatter.format_date(booking.booking_date, lang),
            time=DateFormatter.format_time(booking.booking_date),
            details=details_text
        )
        
        try:
            # Check rate limit before sending
            if not await self.rate_limiter.is_allowed(mechanic.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for mechanic {mechanic.telegram_id}, "
                    f"skipping time confirmed notification"
                )
                return
            
            await self.bot.send_message(mechanic.telegram_id, notification)
            await self.rate_limiter.record_message(mechanic.telegram_id)
        except Exception as e:
            logger.error(f"Failed to notify mechanic {mechanic.telegram_id}: {e}")

    async def _send_time_change_notification(
        self,
        user: User,
        booking: Booking,
        mechanic: User
    ) -> None:
        """Send time change notification"""
        lang = get_user_language(user)
        
        if not booking.proposed_date:
            return
        
        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)
        
        # Format details with proposed_date instead of booking_date
        details_text = get_text("booking.confirm.details", lang).format(
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=DateFormatter.format_date(booking.proposed_date, lang),
            time=DateFormatter.format_time(booking.proposed_date),
            description=booking.get_description(lang) or _("booking.create.no_description")
        )
        
        notification = get_text("booking.notification.time_change", lang).format(
            mechanic_name=mechanic.full_name,
            date=DateFormatter.format_date(booking.proposed_date, lang),
            time=DateFormatter.format_time(booking.proposed_date),
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

