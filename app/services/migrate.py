"""Tiny SQLite migrations: add missing columns and indexes on startup.

A full Alembic setup is overkill for a single database file, yet the app must
not crash on an existing database. We inspect the schema and add what is missing.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("codehog.migrate")

# (table, column, column definition)
REQUIRED_COLUMNS = [
    ("users", "is_admin", "BOOLEAN NOT NULL DEFAULT 0"),
    ("users", "last_bonus_id", "INTEGER NOT NULL DEFAULT 0"),
    ("test_attempts", "experience", "VARCHAR(16) NOT NULL DEFAULT ''"),
    ("items", "tier", "INTEGER NOT NULL DEFAULT 0"),
]

# (table, statement)
INDEXES = [
    (
        "tasks",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_lesson_order ON tasks(lesson_id, order_index)",
    ),
    # One active hedgehog per user (a partial index over rows with is_equipped = 1)
    (
        "inventory",
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uq_inventory_one_active ON inventory(user_id) WHERE is_equipped = 1",
    ),
]

# Retired clothing can no longer be worn. If a user somehow has several
# active skins, keep the most recently acquired one.
CLEANUP_ACTIVE = [
    """UPDATE inventory SET is_equipped = 0 WHERE is_equipped = 1 AND item_id IN (
        SELECT id FROM items WHERE tier = 0)""",
    """UPDATE inventory SET is_equipped = 0 WHERE is_equipped = 1 AND id NOT IN (
        SELECT MAX(id) FROM inventory WHERE is_equipped = 1 GROUP BY user_id)""",
]

CLEANUP_DUPLICATE_TASKS = """
DELETE FROM tasks WHERE id NOT IN (
    SELECT MIN(id) FROM tasks GROUP BY lesson_id, order_index
)
"""


def upgrade_schema(engine: Engine) -> list[str]:
    """Bring an existing database up to the current models. Returns what was changed."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    changes: list[str] = []
    with engine.begin() as connection:
        for table, column, definition in REQUIRED_COLUMNS:
            if table not in tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            if column in existing:
                continue
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
            changes.append(f"{table}.{column}")
    # Unique indexes go on after the cleanup, otherwise creating them would fail.
    with engine.begin() as connection:
        if "tasks" in tables:
            deleted = connection.execute(text(CLEANUP_DUPLICATE_TASKS)).rowcount
            if deleted:
                logger.warning("removed duplicate tasks: %s", deleted)
                changes.append(f"duplicate tasks: -{deleted}")
        if "inventory" in tables:
            for statement in CLEANUP_ACTIVE:
                connection.execute(text(statement))
        for table, statement in INDEXES:
            if table in tables:
                connection.execute(text(statement))

    if changes:
        logger.info("schema upgraded: %s", ", ".join(changes))
    return changes
