"""make_user_language_nullable

Revision ID: 8b223e6f5929
Revises: b5f75dbe4f31
Create Date: 2025-11-25 21:04:32.764613+01:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b223e6f5929'
down_revision = 'b5f75dbe4f31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make language column nullable
    # SQLite doesn't support ALTER COLUMN directly, so we use batch operations
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('language',
                              existing_type=sa.String(10),
                              nullable=True,
                              existing_server_default=None)


def downgrade() -> None:
    # Set default language for NULL values before making it NOT NULL
    # For SQLite, we use batch operations
    op.execute("UPDATE users SET language = 'pl' WHERE language IS NULL")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('language',
                              existing_type=sa.String(10),
                              nullable=False,
                              server_default='pl')

