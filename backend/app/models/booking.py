"""Booking model"""

import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Text,
    Enum as SQLEnum, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class BookingStatus(str, enum.Enum):
    """Booking status enumeration"""
    PENDING = "pending"           # Waiting for mechanic acceptance
    NEGOTIATING = "negotiating"   # Time negotiation in progress
    ACCEPTED = "accepted"         # Accepted by mechanic
    REJECTED = "rejected"         # Rejected by mechanic
    COMPLETED = "completed"       # Service completed
    CANCELLED = "cancelled"       # Cancelled by user


class Booking(Base, TimestampMixin):
    """Booking model - represents service bookings"""
    
    __tablename__ = "bookings"
    
    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign Keys
    creator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    mechanic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Car Information
    car_brand: Mapped[str] = mapped_column(String(100), nullable=False)
    car_model: Mapped[str] = mapped_column(String(100), nullable=False)
    car_number: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Client Information
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Description (multilingual - will be auto-translated)
    description_pl: Mapped[str] = mapped_column(Text, nullable=False)
    description_ru: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Original description language
    original_language: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # Booking DateTime
    booking_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Status
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus),
        default=BookingStatus.PENDING,
        nullable=False
    )
    
    # Negotiation Message ID (for tracking negotiation messages)
    negotiation_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Proposed time during negotiation
    proposed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Notes from mechanic
    mechanic_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Reminder flags
    reminder_3h_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    reminder_1h_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    reminder_30m_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_bookings",
        foreign_keys=[creator_id]
    )
    
    mechanic: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_bookings",
        foreign_keys=[mechanic_id]
    )
    
    service: Mapped["Service"] = relationship(
        "Service",
        back_populates="bookings"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Booking(id={self.id}, car={self.car_brand} {self.car_model}, "
            f"date={self.booking_date}, status={self.status})>"
        )
    
    def get_description(self, language: str = "pl") -> str:
        """Get booking description in specified language"""
        if language == "ru":
            return self.description_ru
        return self.description_pl

