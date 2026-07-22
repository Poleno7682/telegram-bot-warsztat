"""Guards against table name collisions in the shared database.

This project's database can be shared with other, unrelated projects (see
alembic revision 79ffc7ef4513, which had to work around a real collision:
this bot's `users` table matched a different project's table of the same
name). Every table this project owns must end with `_booking_bot`.

app/models/base.py already enforces this at class-definition time for every
declarative model (the earliest possible check). These tests are a second,
independent safety net for two gaps that check doesn't cover:
  - SQLAlchemy Core `Table()` objects defined outside the declarative Base
    (e.g. a future many-to-many association table).
  - Alembic migrations that create/rename a table directly via `op.*`,
    without a corresponding model change.
"""

import re
from pathlib import Path

from app.models.base import Base, TABLE_NAME_SUFFIX

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

# Matches: op.create_table("name", ...) / op.create_table('name', ...)
CREATE_TABLE_RE = re.compile(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]")

# Matches the destination (second) argument of op.rename_table("from", "to")
RENAME_TABLE_RE = re.compile(r"op\.rename_table\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]")

# Migrations written before the _booking_bot naming convention existed (or, for
# 79ffc7ef4513, whose downgrade() intentionally renames back to those old,
# pre-convention names - that's correct, not a violation). Only migrations
# added after this point are held to the naming rule; rewriting historical,
# already-applied migration files is not something to do retroactively.
GRANDFATHERED_MIGRATIONS = {
    "20251122_0004_da6afdecdb90_initial_migration_create_users_services_.py",
    "20251125_0005_add_mechanic_reminder_settings.py",
    "20251125_2104_8b223e6f5929_make_user_language_nullable.py",
    "20251125_2117_3219fc78821b_change_user_language_to_unset_default.py",
    "20260722_0647_79ffc7ef4513_namespace_tables_to_avoid_shared_db_.py",
}


def test_every_orm_table_has_the_project_suffix():
    table_names = list(Base.metadata.tables.keys())

    assert table_names, "Base.metadata has no tables - did model imports change?"
    offenders = [name for name in table_names if not name.endswith(TABLE_NAME_SUFFIX)]

    assert not offenders, (
        f"These tables are missing the {TABLE_NAME_SUFFIX!r} suffix required to avoid "
        f"colliding with other projects in the shared database: {offenders}"
    )


def test_every_migration_created_or_renamed_table_has_the_project_suffix():
    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))
    assert migration_files, "No migration files found - did the alembic/versions path change?"

    offenders: list[str] = []
    for path in migration_files:
        if path.name in GRANDFATHERED_MIGRATIONS:
            continue
        content = path.read_text(encoding="utf-8")
        for table_name in CREATE_TABLE_RE.findall(content):
            if not table_name.endswith(TABLE_NAME_SUFFIX):
                offenders.append(f"{path.name}: create_table({table_name!r})")
        for table_name in RENAME_TABLE_RE.findall(content):
            if not table_name.endswith(TABLE_NAME_SUFFIX):
                offenders.append(f"{path.name}: rename_table(..., {table_name!r})")

    assert not offenders, (
        f"These migrations create/rename a table without the {TABLE_NAME_SUFFIX!r} "
        f"suffix: {offenders}"
    )
