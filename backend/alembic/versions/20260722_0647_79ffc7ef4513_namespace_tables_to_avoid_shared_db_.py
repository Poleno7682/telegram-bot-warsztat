"""namespace_tables_to_avoid_shared_db_collisions

This project's database can be shared with other, unrelated projects on the
same PostgreSQL instance. In practice this caused a real collision on at
least one deployment: this bot's `users` table name matched a completely
different project's `users` table (different columns entirely - no
telegram_id/role/language/etc), and this bot's own `users` table was never
actually created there because Base.metadata.create_all() skips tables that
already exist under that name. `services`, `bookings` and `system_settings`
were not colliding on that deployment and already match this project's
schema.

To make this safe regardless of what else lives in the database, every table
(and the alembic version table, see alembic/env.py) gets a `_booking_bot`
suffix. `services`/`bookings`/`system_settings` are always renamed in place
(no data loss). `users` is only renamed if it's actually *this* project's
table (detected via the `telegram_id` column, which only this schema has);
otherwise it's left untouched (belongs to another project) and
`users_booking_bot` is created fresh instead.

Note: this migration deliberately does NOT add FK constraints from
bookings_booking_bot.creator_id/mechanic_id to users_booking_bot. On the
deployment that motivated this migration, those columns already contain
values (small sequential ids from a users table that no longer exists in its
original form) that don't match any row in the real `users` table currently
live in the shared database - so satisfying a new FK constraint would
require fabricating user data. That FK never actually existed on that
deployment either (verified via pg_constraint before writing this
migration), so omitting it here preserves the exact status quo rather than
introducing new, unrelated data-integrity work into a naming-collision fix.

Revision ID: 79ffc7ef4513
Revises: 3219fc78821b
Create Date: 2026-07-22 06:47:00.375234+02:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '79ffc7ef4513'
down_revision = '3219fc78821b'
branch_labels = None
depends_on = None


def _users_table_belongs_to_this_project(inspector) -> bool:
    """True if a table literally named `users` exists AND looks like this
    project's own users table (only this schema has telegram_id)."""
    if 'users' not in inspector.get_table_names():
        return False
    columns = {col['name'] for col in inspector.get_columns('users')}
    return 'telegram_id' in columns


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)

    # Rename this project's existing tables so they can't collide with
    # another project's tables of the same name in a shared database.
    op.rename_table('services', 'services_booking_bot')
    op.rename_table('bookings', 'bookings_booking_bot')
    op.rename_table('system_settings', 'system_settings_booking_bot')

    users_is_ours = _users_table_belongs_to_this_project(inspector)

    if users_is_ours:
        # Fresh install / no naming collision on this deployment - `users` is
        # genuinely this project's table, rename it like the others.
        op.rename_table('users', 'users_booking_bot')
    else:
        # `users` belongs to a different project (or doesn't exist at all) -
        # create our own under the namespaced name instead of touching it.
        # The `userrole` Postgres enum type may already exist on a shared
        # database from an earlier partial create_all() attempt; reuse it
        # there instead of trying (and failing) to create it again.
        if is_postgres:
            role_enum = postgresql.ENUM('ADMIN', 'MECHANIC', 'USER', name='userrole', create_type=False)
        else:
            role_enum = sa.Enum('ADMIN', 'MECHANIC', 'USER', name='userrole')

        op.create_table(
            'users_booking_bot',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('telegram_id', sa.BigInteger(), nullable=False),
            sa.Column('username', sa.String(length=255), nullable=True),
            sa.Column('first_name', sa.String(length=255), nullable=True),
            sa.Column('last_name', sa.String(length=255), nullable=True),
            sa.Column('role', role_enum, nullable=False),
            sa.Column('language', sa.String(length=10), nullable=False, server_default='unset'),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('reminder_3h_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('reminder_1h_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('reminder_30m_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            op.f('ix_users_booking_bot_telegram_id'),
            'users_booking_bot',
            ['telegram_id'],
            unique=True,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    # Was users_booking_bot created fresh, or renamed from `users`? If a
    # table literally named `users` still exists, this project's table was
    # never renamed away from it - so users_booking_bot must be the fresh one.
    created_fresh = 'users' in inspector.get_table_names()

    if created_fresh:
        op.drop_index(op.f('ix_users_booking_bot_telegram_id'), table_name='users_booking_bot')
        op.drop_table('users_booking_bot')
    else:
        op.rename_table('users_booking_bot', 'users')

    op.rename_table('system_settings_booking_bot', 'system_settings')
    op.rename_table('bookings_booking_bot', 'bookings')
    op.rename_table('services_booking_bot', 'services')
