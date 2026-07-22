"""Base model class"""

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# This project's database can be shared with other, unrelated projects (see
# alembic revision 79ffc7ef4513, which had to work around a real collision:
# this bot's `users` table name matched a different project's table). Every
# table therefore must carry this suffix so it can never collide again.
TABLE_NAME_SUFFIX = "_booking_bot"


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models.

    Enforces TABLE_NAME_SUFFIX on every mapped subclass at class-definition
    time (i.e. at import time, before the app even starts) - the earliest
    point this can realistically be caught. See TABLE_NAME_SUFFIX for why.
    """

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        table_name = cls.__dict__.get("__tablename__")
        # Only mapped classes that declare their own table need checking;
        # abstract/mixin intermediate classes (no __tablename__ of their own)
        # are skipped.
        if table_name is not None and not table_name.endswith(TABLE_NAME_SUFFIX):
            raise AssertionError(
                f"{cls.__name__}.__tablename__ = {table_name!r} must end with "
                f"{TABLE_NAME_SUFFIX!r} - this database is shared with other "
                f"projects and unsuffixed table names can silently collide "
                f"with theirs (see alembic revision 79ffc7ef4513)."
            )


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

