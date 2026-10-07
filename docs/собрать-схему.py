#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает Database_Schema.md прямо из моделей приложения.

Схему, набранную руками, невозможно удержать в согласии с кодом: поля
переименовываются, таблицы добавляются, а документ остаётся прежним.
Поэтому он генерируется из `Base.metadata` — того же источника, из
которого приложение создаёт таблицы. Разойтись они не могут.

    python3 собрать-схему.py [путь/до/Database_Schema.md]
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.models import Base  # noqa: E402
import app.models  # noqa: F401,E402  — регистрирует все таблицы в metadata

# таблица -> (название по-русски, пояснение, объект реального мира?)
ОПИСАНИЯ: dict[str, tuple[str, str, bool]] = {
    "users": ("Ученик", "Человек, который учится. Профиль, игровой баланс и состояние серии.", True),
    "test_attempts": ("Попытка диагностики", "Прохождение вводного теста: ответы, счёт, определённый уровень. У гостя поле user_id пустое, пока он не зарегистрируется.", True),
    "courses": ("Курс", "Персональная программа обучения, собранная под уровень ученика.", True),
    "modules": ("Модуль", "Раздел курса — несколько уроков на одну тему.", True),
    "lessons": ("Урок", "Занятие: теория и набор заданий.", True),
    "tasks": ("Задание", "Конкретный вопрос или задача внутри урока.", True),
    "submissions": ("Решение", "Попытка сдачи: что человек написал, прошло ли и что вернулось.", True),
    "items": ("Скин ежа", "Скин ежа: один из 54 в коллекции — 6 уровней по 9. Уровень N открывается после прохождения модуля N−1.", True),
    "wheel_spins": ("Вращение колеса", "Событие с призом.", True),
    "achievements": ("Медаль", "Награда за поведение: тип условия и порог.", True),
    "memes": ("Мем", "Картинка, которую показывают после пройденного урока.", True),
    "daily_activity": ("День занятий", "Служебная. На ней держится трекер серии и дневной лимит наград.", False),
    "coin_transactions": ("Движение монет", "Служебная. Журнал начислений и трат — источник истины по балансу.", False),
    "inventory": ("Коллекция ежей", "Связующая: «пользователь ↔ скин», многие-ко-многим. Активный ёж у пользователя один. Стартовый ёж, выбранный при регистрации, выдаётся обычной записью — бесплатно и сразу с is_equipped = true.", False),
    "user_achievements": ("Полученные медали", "Связующая: «пользователь ↔ медаль», многие-ко-многим.", False),
    "bonus_grants": ("Массовое начисление", "Служебная. Бонус адресован сразу всем, поэтому внешнего ключа на пользователя намеренно нет.", False),
}

# связи для ERD: (левая, правая, подпись)
СВЯЗИ = [
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

ТИПЫ = {"INTEGER": "int", "VARCHAR": "string", "TEXT": "text", "BOOLEAN": "bool",
        "DATETIME": "datetime", "DATE": "date", "FLOAT": "float", "NUMERIC": "decimal"}


def коротко(столбец) -> str:
    сырой = str(столбец.type).split("(")[0].upper()
    return ТИПЫ.get(сырой, сырой.lower())


def ключи(таблица, столбец) -> str:
    метки = []
    if столбец.primary_key:
        метки.append("PK")
    if столбец.foreign_keys:
        метки.append("FK")
    уникален = столбец.unique or any(
        len(о.columns) == 1 and столбец.name in о.columns
        for о in таблица.constraints if о.__class__.__name__ == "UniqueConstraint"
    )
    if уникален and not столбец.primary_key:
        метки.append("UK")
    return " ".join(метки)


def ссылка(столбец) -> str:
    for вк in столбец.foreign_keys:
        return f"→ `{вк.column.table.name}.{вк.column.name}`"
    return ""


def собрать() -> str:
    таблицы = Base.metadata.tables
    имена = sorted(таблицы)
    реальные = [т for т in имена if ОПИСАНИЯ.get(т, ("", "", False))[2]]
    служебные = [т for т in имена if not ОПИСАНИЯ.get(т, ("", "", False))[2]]

    ч: list[str] = []
    ч.append("# Схема базы данных «CodeHogwarts»")
    ч.append("")
    ч.append(f"**{len(имена)} сущностей**, из них **{len(реальные)} представляют объекты "
             f"реального мира** и {len(служебные)} — служебные и связующие.")
    ч.append("")
    ч.append("> Документ **генерируется** из моделей приложения скриптом "
             "`собрать-схему.py`. Править его руками не нужно: при изменении моделей "
             "он пересобирается и не может разойтись с кодом.")
    ч.append("")

    # ── ERD ──
    ч.append("## ERD")
    ч.append("")
    ч.append("```mermaid")
    ч.append("erDiagram")
    for лев, прав, подпись in СВЯЗИ:
        if лев in таблицы and прав in таблицы:
            ч.append(f'    {лев} ||--o{{ {прав} : "{подпись}"')
    ч.append("")
    for имя in имена:
        т = таблицы[имя]
        ч.append(f"    {имя} {{")
        for с in т.columns:
            к = ключи(т, с)
            ч.append(f"        {коротко(с)} {с.name}{(' ' + к) if к else ''}")
        ч.append("    }")
    ч.append("```")
    ч.append("")

    # ── списки ──
    for заголовок, набор in (("Объекты реального мира", реальные),
                             ("Служебные и связующие", служебные)):
        ч.append(f"### {заголовок} ({len(набор)})")
        ч.append("")
        ч.append("| Таблица | Что моделирует | Пояснение |")
        ч.append("|---|---|---|")
        for имя in набор:
            название, пояснение, _ = ОПИСАНИЯ.get(имя, (имя, "", False))
            ч.append(f"| `{имя}` | {название} | {пояснение} |")
        ч.append("")

    # ── поля ──
    ч.append("## Поля таблиц")
    ч.append("")
    ч.append("Обозначения: **PK** — первичный ключ, **UK** — уникальное значение, "
             "**FK** — внешний ключ, ссылка на другую таблицу.")
    ч.append("")
    for имя in имена:
        т = таблицы[имя]
        название, пояснение, _ = ОПИСАНИЯ.get(имя, (имя, "", False))
        ч.append(f"### `{имя}` — {название}")
        ч.append("")
        ч.append(пояснение)
        ч.append("")
        ч.append("| Поле | Тип | Ключ | Обязательное | Ссылка | Пояснение |")
        ч.append("|---|---|---|---|---|---|")
        for с in т.columns:
            # пояснение берётся из comment= в модели
            ч.append(f"| `{с.name}` | {коротко(с)} | {ключи(т, с) or '—'} | "
                     f"{'да' if not с.nullable else 'нет'} | {ссылка(с) or '—'} | {с.comment or ''} |")
        ограничения = [о for о in т.constraints if о.__class__.__name__ in ("UniqueConstraint", "CheckConstraint")]
        частичные = [и for и in т.indexes if и.unique and и.dialect_options["sqlite"].get("where") is not None]
        if ограничения or частичные:
            ч.append("")
            for о in ограничения:
                if о.__class__.__name__ == "UniqueConstraint":
                    поля = ", ".join(f"`{к.name}`" for к in о.columns)
                    ч.append(f"- **UNIQUE** ({поля}) — сочетание не может повториться.")
                else:
                    ч.append(f"- **CHECK** — `{о.sqltext}`.")
            for и in частичные:
                поля = ", ".join(f"`{к.name}`" for к in и.columns)
                условие = и.dialect_options["sqlite"]["where"]
                ч.append(f"- **UNIQUE** ({поля}) WHERE `{условие}` — среди строк с этим условием значение не повторяется.")
        ч.append("")
    return "\n".join(ч)


def main() -> None:
    куда = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
        pathlib.Path(__file__).parent / "Database_Schema.md"
    текст = собрать()
    куда.write_text(текст, encoding="utf-8")
    print(f"собран {куда}: {len(текст.splitlines())} строк, "
          f"{len(Base.metadata.tables)} таблиц")


if __name__ == "__main__":
    main()
