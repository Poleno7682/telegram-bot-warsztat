"""Scheduler that sends upcoming booking reminders to mechanics"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional
from contextlib import asynccontextmanager

from aiogram import Bot

from app.config.database import AsyncSessionLocal
from app.repositories.booking import BookingRepository
from app.services.notification_service import NotificationService


@dataclass(frozen=True)
class ReminderRule:
    pref_attr: str
    sent_attr: str
    threshold: timedelta
    label_key: str


class ReminderScheduler:
    """Background scheduler that dispatches booking reminders
    
    Can be used as context manager to ensure proper cleanup:
    
    async with ReminderScheduler(bot) as scheduler:
        # scheduler is running
        await asyncio.sleep(60)
    # scheduler is automatically stopped
    """
    
    CHECK_INTERVAL = 60  # seconds
    SEND_WINDOW = timedelta(minutes=5)
    STOP_TIMEOUT = 10.0  # seconds to wait for graceful shutdown
    
    RULES = (
        ReminderRule("reminder_3h_enabled", "reminder_3h_sent", timedelta(hours=3), "booking.reminder.time_left_3h"),
        ReminderRule("reminder_1h_enabled", "reminder_1h_sent", timedelta(hours=1), "booking.reminder.time_left_1h"),
        ReminderRule("reminder_30m_enabled", "reminder_30m_sent", timedelta(minutes=30), "booking.reminder.time_left_30m"),
    )
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._running = False
    
    def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            self.logger.warning("Scheduler is already running")
            return
        
        if not self._task:
            self._task = asyncio.create_task(self._run())
            self._running = True
            self.logger.info("Reminder scheduler started")
    
    async def stop(self, timeout: Optional[float] = None) -> None:
        """
        Stop the scheduler gracefully
        
        Args:
            timeout: Maximum time to wait for shutdown (default: STOP_TIMEOUT)
        """
        if not self._running or not self._task:
            return
        
        self.logger.info("Stopping reminder scheduler...")
        self._stop_event.set()
        
        timeout = timeout or self.STOP_TIMEOUT
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning(f"Scheduler did not stop within {timeout}s, cancelling task")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self._task = None
        self._stop_event.clear()
        self._running = False
        self.logger.info("Reminder scheduler stopped")
    
    async def __aenter__(self) -> "ReminderScheduler":
        """Context manager entry"""
        self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures scheduler is stopped"""
        await self.stop()
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running and self._task is not None
    
    async def _run(self) -> None:
        """Main scheduler loop"""
        self.logger.info("Reminder scheduler loop started")
        try:
            while not self._stop_event.is_set():
                try:
                    await self._process_cycle()
                except Exception as exc:
                    # Log error but continue running
                    self.logger.exception("Reminder scheduler cycle failed: %s", exc)
                    # Wait a bit before retrying to avoid tight error loops
                    await asyncio.sleep(5)
                
                # Wait for next check interval or stop signal
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.CHECK_INTERVAL)
                except asyncio.TimeoutError:
                    # Normal timeout - continue to next cycle
                    continue
        except asyncio.CancelledError:
            self.logger.info("Reminder scheduler loop cancelled")
            raise
        except Exception as exc:
            self.logger.exception("Fatal error in reminder scheduler loop: %s", exc)
            raise
        finally:
            self.logger.info("Reminder scheduler loop ended")
    
    async def _process_cycle(self) -> None:
        """Process one reminder cycle"""
        try:
            async with AsyncSessionLocal() as session:
                repo = BookingRepository(session)
                notification_service = NotificationService(session, self.bot)
                now = datetime.now(timezone.utc)
                
                try:
                    bookings = await repo.get_bookings_for_reminders(now)
                except Exception as e:
                    self.logger.error(f"Failed to fetch bookings for reminders: {e}")
                    return
                
                updated = False
                reminders_sent = 0
                
                for booking in bookings:
                    try:
                        mechanic = booking.mechanic
                        if not mechanic or not mechanic.is_active:
                            continue
                        
                        delta = booking.booking_date - now
                        if delta.total_seconds() <= 0:
                            continue
                        
                        for rule in self.RULES:
                            try:
                                if not getattr(mechanic, rule.pref_attr):
                                    continue
                                if getattr(booking, rule.sent_attr):
                                    continue
                                if not self._should_send(delta, rule.threshold):
                                    continue
                                
                                await notification_service.notify_mechanic_reminder(
                                    booking,
                                    mechanic,
                                    rule.label_key
                                )
                                setattr(booking, rule.sent_attr, True)
                                updated = True
                                reminders_sent += 1
                            except Exception as e:
                                self.logger.error(
                                    f"Failed to send reminder for booking {booking.id}, "
                                    f"rule {rule.label_key}: {e}"
                                )
                                # Continue with next rule/booking
                                continue
                    except Exception as e:
                        self.logger.error(f"Error processing booking {booking.id}: {e}")
                        # Continue with next booking
                        continue
                
                if updated:
                    try:
                        await session.commit()
                        if reminders_sent > 0:
                            self.logger.debug(f"Sent {reminders_sent} reminder(s) in this cycle")
                    except Exception as e:
                        self.logger.error(f"Failed to commit reminder updates: {e}")
                        await session.rollback()
        except Exception as e:
            self.logger.error(f"Error in reminder cycle: {e}")
            raise
    
    def _should_send(self, delta: timedelta, threshold: timedelta) -> bool:
        """Return True if delta is within threshold window"""
        lower_bound = threshold - self.SEND_WINDOW
        return lower_bound <= delta <= threshold + self.SEND_WINDOW

