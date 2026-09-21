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
]


ИНДЕКСЫ = [
    ("uq_task_lesson_order", "CREATE UNIQUE INDEX IF NOT EXISTS "
                             "uq_task_lesson_order ON tasks(lesson_id, order_index)"),
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
            for имя, запрос in ИНДЕКСЫ:
                соединение.execute(text(запрос))

    if добавлено:
        лог.info("схема дополнена: %s", ", ".join(добавлено))
    return добавлено
