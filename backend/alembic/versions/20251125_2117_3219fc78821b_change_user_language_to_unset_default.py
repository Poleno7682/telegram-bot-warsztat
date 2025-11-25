"""change_user_language_to_unset_default

Revision ID: 3219fc78821b
Revises: 8b223e6f5929
Create Date: 2025-11-25 21:17:09.397131+01:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3219fc78821b'
down_revision = '8b223e6f5929'
branch_labels = None
depends_on = None

# Special value for unset language
LANGUAGE_UNSET = "unset"


def upgrade() -> None:
    # Update all NULL values to "unset"
    op.execute(f"UPDATE users SET language = '{LANGUAGE_UNSET}' WHERE language IS NULL")
    
    # Change column to NOT NULL with default value "unset"
    # SQLite doesn't support ALTER COLUMN directly, so we use batch operations
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('language',
                              existing_type=sa.String(10),
                              nullable=False,
                              server_default=LANGUAGE_UNSET)


def downgrade() -> None:
    # Remove default and make nullable again
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('language',
                              existing_type=sa.String(10),
                              nullable=True,
                              existing_server_default=LANGUAGE_UNSET)
    
    # Set NULL values back to NULL (optional - can leave as "unset")
    # op.execute("UPDATE users SET language = NULL WHERE language = 'unset'")
