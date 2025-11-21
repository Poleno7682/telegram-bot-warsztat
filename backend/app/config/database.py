"""Database configuration and session management"""

from typing import AsyncGenerator
from pathlib import Path
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from .settings import get_settings


settings = get_settings()

# Handle SQLite paths - make them absolute relative to backend directory
database_url = settings.database_url
if "sqlite" in database_url:
    # Extract path from URL (format: sqlite+aiosqlite:///./db/bot.db)
    db_path = database_url.split("///")[-1]
    
    # If path is relative, make it absolute relative to backend directory
    if not Path(db_path).is_absolute():
        backend_dir = Path(__file__).resolve().parent.parent.parent
        db_absolute_path = backend_dir / db_path.lstrip("./")
        
        # Create directory if it doesn't exist
        db_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Reconstruct URL with absolute path
        database_url = f"sqlite+aiosqlite:///{db_absolute_path}"

# Create async engine
engine: AsyncEngine = create_async_engine(
    database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,
    poolclass=NullPool if "sqlite" in database_url else AsyncAdaptedQueuePool,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database - create all tables"""
    from app.models.base import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connection"""
    await engine.dispose()

