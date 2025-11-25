"""Add mechanic reminder preferences and booking reminder flags

Revision ID: b5f75dbe4f31
Revises: da6afdecdb90
Create Date: 2025-11-25 12:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'b5f75dbe4f31'
down_revision = 'da6afdecdb90'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add reminder preferences to users (only if they don't exist)
    if not column_exists('users', 'reminder_3h_enabled'):
        op.add_column(
            'users',
            sa.Column('reminder_3h_enabled', sa.Boolean(), nullable=False, server_default=sa.true())
        )
    if not column_exists('users', 'reminder_1h_enabled'):
        op.add_column(
            'users',
            sa.Column('reminder_1h_enabled', sa.Boolean(), nullable=False, server_default=sa.true())
        )
    if not column_exists('users', 'reminder_30m_enabled'):
        op.add_column(
            'users',
            sa.Column('reminder_30m_enabled', sa.Boolean(), nullable=False, server_default=sa.true())
        )

    # Add reminder flags to bookings (only if they don't exist)
    if not column_exists('bookings', 'reminder_3h_sent'):
        op.add_column(
            'bookings',
            sa.Column('reminder_3h_sent', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    if not column_exists('bookings', 'reminder_1h_sent'):
        op.add_column(
            'bookings',
            sa.Column('reminder_1h_sent', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    if not column_exists('bookings', 'reminder_30m_sent'):
        op.add_column(
            'bookings',
            sa.Column('reminder_30m_sent', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # Note: SQLite doesn't support ALTER COLUMN ... DROP DEFAULT
    # Server defaults are kept for SQLite compatibility
    # For PostgreSQL, you can drop defaults in a separate migration if needed


def downgrade() -> None:
    op.drop_column('bookings', 'reminder_30m_sent')
    op.drop_column('bookings', 'reminder_1h_sent')
    op.drop_column('bookings', 'reminder_3h_sent')
    op.drop_column('users', 'reminder_30m_enabled')
    op.drop_column('users', 'reminder_1h_enabled')
    op.drop_column('users', 'reminder_3h_enabled')

