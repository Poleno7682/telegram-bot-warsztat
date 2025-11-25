"""User model"""

import enum
from typing import List, Optional
from sqlalchemy import BigInteger, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    MECHANIC = "mechanic"
    USER = "user"


class User(Base, TimestampMixin):
    """User model"""
    
    __tablename__ = "users"
    
    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Telegram ID (unique identifier from Telegram)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    
    # User Information
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Role
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.USER
    )
    
    # Language preference (None means not set yet)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Active status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Reminder preferences
    reminder_3h_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    reminder_1h_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    reminder_30m_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Relationships
    created_bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="creator",
        foreign_keys="Booking.creator_id"
    )
    
    assigned_bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="mechanic",
        foreign_keys="Booking.mechanic_id"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p)
        return name or self.username or f"User_{self.telegram_id}"

