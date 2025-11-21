"""Service model"""

from typing import List, Optional
from sqlalchemy import String, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Service(Base, TimestampMixin):
    """Service model - represents auto repair services"""
    
    __tablename__ = "services"
    
    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Service names (multilingual)
    name_pl: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Service description (optional, multilingual)
    description_pl: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description_ru: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Duration in minutes
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Price (optional)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Active status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Relationships
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="service"
    )
    
    def __repr__(self) -> str:
        return f"<Service(id={self.id}, name_pl={self.name_pl}, duration={self.duration_minutes}min)>"
    
    def get_name(self, language: str = "pl") -> str:
        """Get service name in specified language"""
        if language == "ru":
            return self.name_ru
        return self.name_pl
    
    def get_description(self, language: str = "pl") -> Optional[str]:
        """Get service description in specified language"""
        if language == "ru":
            return self.description_ru
        return self.description_pl

