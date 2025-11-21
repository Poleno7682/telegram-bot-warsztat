"""System settings model"""

from typing import Optional
from sqlalchemy import String, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column
from datetime import time

from .base import Base, TimestampMixin


class SystemSettings(Base, TimestampMixin):
    """System settings model - singleton table for system configuration"""
    
    __tablename__ = "system_settings"
    
    # Primary Key (should always be 1 for singleton)
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    
    # Working Hours
    work_start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(8, 0)  # 08:00
    )
    
    work_end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        default=time(16, 0)  # 16:00
    )
    
    # Time step for booking slots (in minutes)
    time_step_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10
    )
    
    # Buffer time between bookings (in minutes)
    buffer_time_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15
    )
    
    # Timezone
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Europe/Warsaw"
    )
    
    # Days to show for booking (how many days ahead)
    booking_days_ahead: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=14  # 2 weeks ahead
    )
    
    def __repr__(self) -> str:
        return (
            f"<SystemSettings(work_hours={self.work_start_time}-{self.work_end_time}, "
            f"step={self.time_step_minutes}min, buffer={self.buffer_time_minutes}min)>"
        )

