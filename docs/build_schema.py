#!/usr/bin/env python3
"""Build Database_Schema.md straight from the application models.

A schema typed by hand cannot be kept in sync with the code: fields get
renamed, tables get added, and the document stays the same. So it is
generated from `Base.metadata`, the same source the app creates its tables
from. The two cannot drift apart.

Table and field descriptions below are documentation content and stay in
Russian, like the rest of the project documentation.

    python3 build_schema.py [path/to/Database_Schema.md]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402, F401  registers every table in the metadata
from app.models import Base  # noqa: E402

# table -> (Russian name, description, is it a real-world object?)
DESCRIPTIONS: dict[str, tuple[str, str, bool]] = {
    "users": (
        "Ученик",
        "Человек, который учится. Профиль, игровой баланс и состояние серии.",
        True,
    ),
    "test_attempts": (
        "Попытка диагностики",
        "Прохождение вводного теста: ответы, счёт, определённый уровень. "
        "У гостя поле user_id пустое, пока он не зарегистрируется.",
        True,
    ),
    "courses": ("Курс", "Персональная программа обучения, собранная под уровень ученика.", True),
    "modules": ("Модуль", "Раздел курса — несколько уроков на одну тему.", True),
    "lessons": ("Урок", "Занятие: теория и набор заданий.", True),
    "tasks": ("Задание", "Конкретный вопрос или задача внутри урока.", True),
    "submissions": (
        "Решение",
        "Попытка сдачи: что человек написал, прошло ли и что вернулось.",
        True,
    ),
    "items": (
        "Скин ежа",
        "Скин ежа: один из 54 в коллекции — 6 уровней по 9. "
        "Уровень N открывается после прохождения модуля N−1.",
        True,
    ),
    "wheel_spins": ("Вращение колеса", "Событие с призом.", True),
    "achievements": ("Медаль", "Награда за поведение: тип условия и порог.", True),
    "memes": ("Мем", "Картинка, которую показывают после пройденного урока.", True),
    "daily_activity": (
        "День занятий",
        "Служебная. На ней держится трекер серии и дневной лимит наград.",
        False,
    ),
    "coin_transactions": (
        "Движение монет",
        "Служебная. Журнал начислений и трат — источник истины по балансу.",
        False,
    ),
    "inventory": (
        "Коллекция ежей",
        "Связующая: «пользователь ↔ скин», многие-ко-многим. Активный ёж у пользователя один. "
        "Стартовый ёж, выбранный при регистрации, выдаётся обычной записью — "
        "бесплатно и сразу с is_equipped = true.",
        False,
    ),
    "user_achievements": (
        "Полученные медали",
        "Связующая: «пользователь ↔ медаль», многие-ко-многим.",
        False,
    ),
    "bonus_grants": (
        "Массовое начисление",
        "Служебная. Бонус адресован сразу всем, поэтому внешнего ключа "
        "на пользователя намеренно нет.",
        False,
    ),
}

# (table, column) -> note shown in the field table
FIELD_NOTES: dict[tuple[str, str], str] = {
    ("items", "sku"): "Код скина: hog-{уровень}-{номер}",
    ("items", "slot"): "Для скинов всегда skin. Другие значения — от старого каталога одежды",
    ("items", "price"): "Цена в монетах",
    ("items", "asset_key"): "Имя картинки: static/img/skins/{asset_key}.webp",
    ("items", "is_active"): "false — снят с продажи, покупки сохраняются",
    ("items", "tier"): (
        "Уровень коллекции 1–6: уровень N открывается после модуля N−1. 0 — старая одежда"
    ),
    ("inventory", "is_equipped"): "Активный ёж. У пользователя не больше одной записи с true",
    ("test_attempts", "experience"): (
        "Опыт до курса: none — не программировал, other — другой язык, python"
    ),
}

# ERD relations: (left, right, label)
RELATIONS = [
    ("users", "test_attempts", "проходил"),
    ("users", "courses", "учится по"),
    ("users", "submissions", "отправлял"),
    ("users", "inventory", "владеет"),
    ("users", "wheel_spins", "крутил"),
    ("users", "daily_activity", "занимался в день"),
    ("users", "coin_transactions", "движение монет"),
    ("users", "user_achievements", "получил"),
    ("courses", "modules", "состоит из"),
    ("modules", "lessons", "содержит"),
    ("lessons", "tasks", "содержит"),
    ("tasks", "submissions", "решается через"),
    ("items", "inventory", "в коллекциях"),
    ("achievements", "user_achievements", "выдаётся через"),
]

TYPES = {
    "INTEGER": "int",
    "VARCHAR": "string",
    "TEXT": "text",
    "BOOLEAN": "bool",
    "DATETIME": "datetime",
    "DATE": "date",
    "FLOAT": "float",
    "NUMERIC": "decimal",
}


def short_type(column) -> str:
    raw = str(column.type).split("(")[0].upper()
    return TYPES.get(raw, raw.lower())


def key_flags(table, column) -> str:
    """PK, FK and UK marks for a column."""
    flags = []
    if column.primary_key:
        flags.append("PK")
    if column.foreign_keys:
        flags.append("FK")
    is_unique = column.unique or any(
        len(constraint.columns) == 1 and column.name in constraint.columns
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )
    if is_unique and not column.primary_key:
        flags.append("UK")
    return " ".join(flags)


def reference(column) -> str:
    for fk in column.foreign_keys:
        return f"→ `{fk.column.table.name}.{fk.column.name}`"
    return ""


def build() -> str:
    tables = Base.metadata.tables
    names = sorted(tables)
    real = [name for name in names if DESCRIPTIONS.get(name, ("", "", False))[2]]
    auxiliary = [name for name in names if not DESCRIPTIONS.get(name, ("", "", False))[2]]

    out: list[str] = []
    out.append("# Схема базы данных «CodeHogwarts»")
    out.append("")
    out.append(
        f"**{len(names)} сущностей**, из них **{len(real)} представляют объекты "
        f"реального мира** и {len(auxiliary)} — служебные и связующие."
    )
    out.append("")
    out.append(
        "> Документ **генерируется** из моделей приложения скриптом "
        "`build_schema.py`. Править его руками не нужно: при изменении моделей "
        "он пересобирается и не может разойтись с кодом."
    )
    out.append("")

    # ── ERD ──
    out.append("## ERD")
    out.append("")
    out.append("```mermaid")
    out.append("erDiagram")
    for left, right, label in RELATIONS:
        if left in tables and right in tables:
            out.append(f'    {left} ||--o{{ {right} : "{label}"')
    out.append("")
    for name in names:
        table = tables[name]
        out.append(f"    {name} {{")
        for column in table.columns:
            flags = key_flags(table, column)
            out.append(
                f"        {short_type(column)} {column.name}{(' ' + flags) if flags else ''}"
            )
        out.append("    }")
    out.append("```")
    out.append("")

    # ── table lists ──
    for heading, group in (
        ("Объекты реального мира", real),
        ("Служебные и связующие", auxiliary),
    ):
        out.append(f"### {heading} ({len(group)})")
        out.append("")
        out.append("| Таблица | Что моделирует | Пояснение |")
        out.append("|---|---|---|")
        for name in group:
            title, note, _ = DESCRIPTIONS.get(name, (name, "", False))
            out.append(f"| `{name}` | {title} | {note} |")
        out.append("")

    # ── fields ──
    out.append("## Поля таблиц")
    out.append("")
    out.append(
        "Обозначения: **PK** — первичный ключ, **UK** — уникальное значение, "
        "**FK** — внешний ключ, ссылка на другую таблицу."
    )
    out.append("")
    for name in names:
        table = tables[name]
        title, note, _ = DESCRIPTIONS.get(name, (name, "", False))
        out.append(f"### `{name}` — {title}")
        out.append("")
        out.append(note)
        out.append("")
        out.append("| Поле | Тип | Ключ | Обязательное | Ссылка | Пояснение |")
        out.append("|---|---|---|---|---|---|")
        for column in table.columns:
            out.append(
                f"| `{column.name}` | {short_type(column)} | {key_flags(table, column) or '—'} | "
                f"{'да' if not column.nullable else 'нет'} | {reference(column) or '—'} | "
                f"{FIELD_NOTES.get((name, column.name), '')} |"
            )
        constraints = [
            constraint
            for constraint in table.constraints
            if constraint.__class__.__name__ in ("UniqueConstraint", "CheckConstraint")
        ]
        partial = [
            index
            for index in table.indexes
            if index.unique and index.dialect_options["sqlite"].get("where") is not None
        ]
        if constraints or partial:
            out.append("")
            for constraint in constraints:
                if constraint.__class__.__name__ == "UniqueConstraint":
                    cols = ", ".join(f"`{col.name}`" for col in constraint.columns)
                    out.append(f"- **UNIQUE** ({cols}) — сочетание не может повториться.")
                else:
                    out.append(f"- **CHECK** — `{constraint.sqltext}`.")
            for index in partial:
                cols = ", ".join(f"`{col.name}`" for col in index.columns)
                where = index.dialect_options["sqlite"]["where"]
                out.append(
                    f"- **UNIQUE** ({cols}) WHERE `{where}` — среди строк с этим условием "
                    "значение не повторяется."
                )
        out.append("")
    return "\n".join(out)


def main() -> None:
    target = (
        pathlib.Path(sys.argv[1])
        if len(sys.argv) > 1
        else pathlib.Path(__file__).parent / "Database_Schema.md"
    )
    text = build()
    target.write_text(text, encoding="utf-8")
    print(f"built {target}: {len(text.splitlines())} lines, {len(Base.metadata.tables)} tables")


if __name__ == "__main__":
    main()
