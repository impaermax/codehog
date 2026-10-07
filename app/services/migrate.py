"""Крошечные миграции для SQLite: добавляем недостающие колонки на старте.

Полноценный Alembic для одного файла базы избыточен, но и ронять приложение
на существующей базе нельзя. Проверяем схему и дописываем то, чего нет.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

лог = logging.getLogger("codehog.migrate")

# таблица -> (колонка, определение)
НУЖНЫЕ = [
    ("users", "is_admin", "BOOLEAN NOT NULL DEFAULT 0"),
    ("users", "last_bonus_id", "INTEGER NOT NULL DEFAULT 0"),
    ("test_attempts", "experience", "VARCHAR(16) NOT NULL DEFAULT ''"),
    ("items", "tier", "INTEGER NOT NULL DEFAULT 0"),
]


ИНДЕКСЫ = [
    ("uq_task_lesson_order", "CREATE UNIQUE INDEX IF NOT EXISTS "
                             "uq_task_lesson_order ON tasks(lesson_id, order_index)"),
    # активный ёж у пользователя один (частичный индекс: только строки is_equipped = 1)
    ("uq_inventory_one_active", "CREATE UNIQUE INDEX IF NOT EXISTS "
                                "uq_inventory_one_active ON inventory(user_id) WHERE is_equipped = 1"),
]

# Старая одежда снята с продажи, носить её больше нельзя. А если у кого-то
# активными оказались несколько скинов, оставляем последний полученный.
ЧИСТКА_АКТИВНЫХ = [
    """UPDATE inventory SET is_equipped = 0 WHERE is_equipped = 1 AND item_id IN (
        SELECT id FROM items WHERE tier = 0)""",
    """UPDATE inventory SET is_equipped = 0 WHERE is_equipped = 1 AND id NOT IN (
        SELECT MAX(id) FROM inventory WHERE is_equipped = 1 GROUP BY user_id)""",
]

ЧИСТКА_ДУБЛЕЙ = """
DELETE FROM tasks WHERE id NOT IN (
    SELECT MIN(id) FROM tasks GROUP BY lesson_id, order_index
)
"""


def дополнить_схему(engine: Engine) -> list[str]:
    инспектор = inspect(engine)
    добавлено: list[str] = []
    with engine.begin() as соединение:
        for таблица, колонка, определение in НУЖНЫЕ:
            if таблица not in инспектор.get_table_names():
                continue
            есть = {к["name"] for к in инспектор.get_columns(таблица)}
            if колонка in есть:
                continue
            соединение.execute(text(f"ALTER TABLE {таблица} ADD COLUMN {колонка} {определение}"))
            добавлено.append(f"{таблица}.{колонка}")
    # уникальные индексы навешиваем после чистки дублей, иначе создание упадёт
    with engine.begin() as соединение:
        if "tasks" in инспектор.get_table_names():
            удалено = соединение.execute(text(ЧИСТКА_ДУБЛЕЙ)).rowcount
            if удалено:
                лог.warning("удалено задвоенных заданий: %s", удалено)
                добавлено.append(f"дубли заданий: -{удалено}")
        if "inventory" in инспектор.get_table_names():
            for запрос in ЧИСТКА_АКТИВНЫХ:
                соединение.execute(text(запрос))
        for имя, запрос in ИНДЕКСЫ:
            таблица = запрос.split(" ON ")[1].split("(")[0]
            if таблица in инспектор.get_table_names():
                соединение.execute(text(запрос))

    if добавлено:
        лог.info("схема дополнена: %s", ", ".join(добавлено))
    return добавлено
