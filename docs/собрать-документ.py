#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает из отдельных документов один файл — Markdown и Word.

Блоки mermaid заменяются на заранее отрисованные картинки: в Word диаграммы
из текста не рендерятся, а на защите они нужны.

    python3 собрать-документ.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ЗДЕСЬ = pathlib.Path(__file__).parent
ПОРЯДОК = [
    "01-контекст.md", "02-требования.md", "03-архитектура.md",
    "04-модель-данных.md", "05-api.md", "06-команда-и-план.md",
    "07-риски.md", "08-развёртывание.md",
    "09-стек-и-репозиторий.md",
]
# (файл, номер блока) -> (картинка, подпись)
КАРТИНКИ = {
    ("01-контекст.md", 1): ("uc.png", "Диаграмма вариантов использования"),
    ("03-архитектура.md", 1): ("arch.png", "Общая схема приложения"),
    ("03-архитектура.md", 2): ("classes.png", "Диаграмма классов"),
    ("03-архитектура.md", 3): ("seq.png", "Последовательность: проверка кода"),
    ("04-модель-данных.md", 1): ("erd.png", "ERD — модель данных"),
}

ШАПКА = """---
title: "CodeHogwarts — проектная документация"
subtitle: "Лабораторные работы 2 семестра по дисциплине «Объектно-ориентированное программирование»"
lang: ru
toc: true
toc-depth: 2
---

Клиент-серверное веб-приложение: игровой тренажёр программирования на Python.

**Рабочий стенд:** https://maks.my

"""


def подставить_картинки(текст: str, файл: str) -> str:
    счётчик = 0

    def замена(совпадение: re.Match) -> str:
        nonlocal счётчик
        счётчик += 1
        ключ = (файл, счётчик)
        if ключ not in КАРТИНКИ:
            return совпадение.group(0)
        картинка, подпись = КАРТИНКИ[ключ]
        return f"![{подпись}](диаграммы/{картинка})\n"

    return re.sub(r"```mermaid\n.*?```", замена, текст, flags=re.S)


def собрать() -> str:
    части = [ШАПКА]
    for имя in ПОРЯДОК:
        путь = ЗДЕСЬ / имя
        if not путь.exists():
            print(f"пропущен {имя}: файла нет")
            continue
        текст = путь.read_text(encoding="utf-8")
        # ссылки между документами в едином файле не нужны
        текст = re.sub(r"\[([^\]]+)\]\(\d\d-[^)]+\.md(#[^)]*)?\)", r"\1", текст)
        части.append(подставить_картинки(текст, имя))
    return "\n\n\\newpage\n\n".join(части)


def main() -> None:
    единый = ЗДЕСЬ / "CodeHogwarts-документация.md"
    единый.write_text(собрать(), encoding="utf-8")
    print(f"собран {единый.name}: {len(единый.read_text(encoding='utf-8').splitlines())} строк")

    docx = ЗДЕСЬ / "CodeHogwarts-документация.docx"
    итог = subprocess.run(
        ["pandoc", str(единый), "-o", str(docx),
         "--resource-path", str(ЗДЕСЬ), "--toc", "--toc-depth=2"],
        capture_output=True, text=True,
    )
    if итог.returncode == 0:
        print(f"собран {docx.name}: {docx.stat().st_size // 1024} КБ")
    else:
        print("pandoc не справился:", итог.stderr[:300])


if __name__ == "__main__":
    main()
