"""Alembic environment configuration"""

import asyncio
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import models and Base
from app.models.base import Base, TABLE_NAME_SUFFIX
from app.models.user import User
from app.models.service import Service
from app.models.booking import Booking
from app.models.settings import SystemSettings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Resolve the DB URL exactly like the app does (app/config/database.py), instead of
# reading os.getenv("DATABASE_URL") directly: when DATABASE_URL is unset/empty and
# DB_HOST/DB_USER/DB_NAME are set instead (as in this project's .env), a raw
# os.getenv("DATABASE_URL", "<sqlite fallback>") returns "" (the var IS set, just
# empty) instead of falling back - which then fails to parse as a SQLAlchemy URL.
from app.config.settings import get_settings
database_url = get_settings().get_database_url()
config.set_main_option("sqlalchemy.url", database_url)

# The database can be shared with other, unrelated projects (see alembic
# revision 79ffc7ef4513) - use a namespaced version table so this project's
# migration history can't collide with another project's alembic_version row.
VERSION_TABLE = "alembic_version_booking_bot"


def include_object(object, name, type_, reflected, compare_to) -> bool:
    """Keep autogenerate from ever looking at tables that aren't ours.

    Since the database can be shared with other projects, `--autogenerate`
    reflects EVERY table actually present (theirs included) and diffs it
    against target_metadata (which only has our models). Without this
    filter, autogenerate would propose `DROP TABLE` for another project's
    tables just because they're not in our metadata - excluding anything
    that isn't one of our namespaced tables makes that structurally
    impossible.
    """
    if type_ == "table":
        return name is not None and name.endswith(TABLE_NAME_SUFFIX)
    # For columns/indexes/constraints, `object.table.name` is the owning
    # table - only compare those that belong to one of our own tables.
    table = getattr(object, "table", None)
    if table is not None:
        return table.name.endswith(TABLE_NAME_SUFFIX)
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        version_table=VERSION_TABLE,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a connection"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_table=VERSION_TABLE,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine"""
    
    # Create directory for SQLite database if needed
    db_url = config.get_main_option("sqlalchemy.url")
    if "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    # Create async engine
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

