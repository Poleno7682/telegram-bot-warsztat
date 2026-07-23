"""Notification Service - Handles sending notifications to users"""

from typing import Any, List, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.user import User
from app.repositories.user import UserRepository
from app.core.i18n import get_text
from app.core.rate_limiter import get_notification_rate_limiter
from app.core.logging_config import get_logger
from app.core.deferred_message_manager import get_deferred_message_manager
from app.utils.date_formatter import DateFormatter
from app.utils.booking_utils import format_booking_details
from app.utils.user_utils import get_user_language
from app.bot.ui.menu import build_menu_payload, schedule_main_menu_return

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
        schedule_main_menu_return(self.bot, booking.creator.telegram_id, booking.creator, delay=3.0)

        # Send confirmation message to mechanic with main menu
        # Cancel any scheduled menu return for mechanic to prevent duplicate
        manager = get_deferred_message_manager()
        await manager.cancel_message(mechanic.telegram_id)

        lang = get_user_language(mechanic)
        confirmation_text = get_text("booking.notification.accepted_mechanic", lang, default="✅ Запись принята")

        # Get main menu text and keyboard
        menu_text, keyboard = build_menu_payload(mechanic)
        
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
    
    async def _send_simple_notification(
        self,
        recipient: User,
        text_key: str,
        *,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        error_label: str = "notification",
        **format_kwargs: Any,
    ) -> bool:
        """
        Format `text_key` for recipient's language and send it, honoring the
        notification rate limit.

        Centralizes the send template shared by every notify_* method below:
        resolve language -> format text -> check rate limit -> send -> log
        errors. Kept as one place so all notification types behave the same
        way under rate limiting / delivery failures.

        Args:
            recipient: User to notify
            text_key: i18n key for the notification text
            reply_markup: Optional keyboard to attach
            error_label: Human-readable label used in warning/error logs
            **format_kwargs: Values to interpolate into the translated text

        Returns:
            True if the message was delivered, or the recipient is
            permanently unreachable (blocked the bot / chat gone), so
            retrying would never succeed. False if the send was skipped
            (rate limit) or failed transiently (network, Telegram-side
            error) - callers that track "was this sent" (e.g. reminder
            scheduling) should treat False as "try again later", not as
            delivered.
        """
        lang = get_user_language(recipient)
        notification = get_text(text_key, lang).format(**format_kwargs)

        try:
            if not await self.rate_limiter.is_allowed(recipient.telegram_id):
                logger.warning(
                    f"Rate limit exceeded for {recipient.telegram_id}, "
                    f"skipping {error_label}"
                )
                return False

            await self.bot.send_message(recipient.telegram_id, notification, reply_markup=reply_markup)
            await self.rate_limiter.record_message(recipient.telegram_id)
            return True
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            # Recipient blocked the bot / chat no longer exists - this will
            # never succeed on retry, so treat it as "handled".
            logger.warning(f"Recipient permanently unreachable for {error_label} to {recipient.telegram_id}: {e}")
            return True
        except Exception as e:
            logger.error(f"Failed to send {error_label} to {recipient.telegram_id}: {e}")
            return False

    async def _send_new_booking_notification(
        self,
        user: User,
        booking: Booking
    ) -> None:
        """Send new booking notification to user"""
        lang = get_user_language(user)

        from app.bot.keyboards.inline import get_booking_actions_keyboard

        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)

        await self._send_simple_notification(
            user,
            "booking.notification.new_booking",
            reply_markup=get_booking_actions_keyboard(booking.id, _),
            error_label="new booking notification",
            user_name=booking.creator.full_name,
            brand=booking.car_brand,
            model=booking.car_model,
            number=booking.car_number,
            client_name=booking.client_name,
            client_phone=booking.client_phone,
            service=booking.service.get_name(lang),
            date=DateFormatter.format_date(booking.booking_date, lang),
            time=DateFormatter.format_time(booking.booking_date),
            description=booking.get_description(lang),
        )

    async def notify_mechanic_reminder(
        self,
        booking: Booking,
        mechanic: User,
        time_label_key: str
    ) -> bool:
        """
        Send reminder notification to assigned mechanic.

        Returns:
            See _send_simple_notification - callers should only mark the
            reminder as sent when this returns True.
        """
        lang = get_user_language(mechanic)
        time_left = get_text(time_label_key, lang)

        def _(key: str, **kwargs) -> str:
            return get_text(key, lang, **kwargs)

        details_text = format_booking_details(booking, lang, _)

        return await self._send_simple_notification(
            mechanic,
            "booking.notification.reminder",
            error_label="reminder notification",
            time_left=time_left,
            details=details_text,
        )

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

        await self._send_simple_notification(
            user,
            "booking.notification.accepted",
            error_label="notification",
            mechanic_name=mechanic.full_name,
            details=details_text,
        )

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

        await self._send_simple_notification(
            user,
            "booking.notification.rejected",
            error_label="notification",
            mechanic_name=mechanic.full_name,
            details=details_text,
        )

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

        await self._send_simple_notification(
            mechanic,
            "booking.notification.time_confirmed",
            error_label="time confirmed notification",
            user_name=user.full_name,
            date=DateFormatter.format_date(booking.booking_date, lang),
            time=DateFormatter.format_time(booking.booking_date),
            details=details_text,
        )

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

        from app.bot.keyboards.inline import get_confirmation_keyboard

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

        await self._send_simple_notification(
            user,
            "booking.notification.time_change",
            reply_markup=get_confirmation_keyboard(booking.id, _, show_change_time=True),
            error_label="time change notification",
            mechanic_name=mechanic.full_name,
            date=DateFormatter.format_date(booking.proposed_date, lang),
            time=DateFormatter.format_time(booking.proposed_date),
            details=details_text,
        )

