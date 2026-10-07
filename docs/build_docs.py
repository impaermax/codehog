#!/usr/bin/env python3
"""Combine the separate documents into one file, in Markdown and Word.

Mermaid blocks are replaced with pre-rendered images: Word cannot render
diagrams from text.

    python3 build_docs.py
"""

from __future__ import annotations

import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).parent
ORDER = [
    "01-контекст.md",
    "02-требования.md",
    "03-архитектура.md",
    "04-модель-данных.md",
    "05-api.md",
    "06-команда-и-план.md",
    "07-риски.md",
    "08-развёртывание.md",
    "09-стек-и-репозиторий.md",
]
# (file, mermaid block number) -> (image, caption)
IMAGES = {
    ("01-контекст.md", 1): ("uc.png", "Диаграмма вариантов использования"),
    ("03-архитектура.md", 1): ("arch.png", "Общая схема приложения"),
    ("03-архитектура.md", 2): ("classes.png", "Диаграмма классов"),
    ("03-архитектура.md", 3): ("seq.png", "Последовательность: проверка кода"),
    ("04-модель-данных.md", 1): ("erd.png", "ERD — модель данных"),
}

COURSE_NAME = "«Объектно-ориентированное программирование»"
SUBTITLE = f"Лабораторные работы 2 семестра по дисциплине {COURSE_NAME}"

HEADER = f"""---
title: "CodeHogwarts — проектная документация"
subtitle: "{SUBTITLE}"
lang: ru
toc: true
toc-depth: 2
---

Клиент-серверное веб-приложение: игровой тренажёр программирования на Python.

**Рабочий стенд:** https://maks.my/codehog/

"""


def insert_images(text: str, filename: str) -> str:
    """Replace the mermaid blocks of a document with their rendered images."""
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        key = (filename, counter)
        if key not in IMAGES:
            return match.group(0)
        image, caption = IMAGES[key]
        return f"![{caption}](диаграммы/{image})\n"

    return re.sub(r"```mermaid\n.*?```", replace, text, flags=re.S)


def build() -> str:
    parts = [HEADER]
    for name in ORDER:
        path = HERE / name
        if not path.exists():
            print(f"skipped {name}: file not found")
            continue
        text = path.read_text(encoding="utf-8")
        # Links between documents make no sense in a single file
        text = re.sub(r"\[([^\]]+)\]\(\d\d-[^)]+\.md(#[^)]*)?\)", r"\1", text)
        parts.append(insert_images(text, name))
    return "\n\n\\newpage\n\n".join(parts)


def main() -> None:
    combined = HERE / "CodeHogwarts-документация.md"
    combined.write_text(build(), encoding="utf-8")
    lines = len(combined.read_text(encoding="utf-8").splitlines())
    print(f"built {combined.name}: {lines} lines")

    docx = HERE / "CodeHogwarts-документация.docx"
    result = subprocess.run(
        [
            "pandoc",
            str(combined),
            "-o",
            str(docx),
            "--resource-path",
            str(HERE),
            "--toc",
            "--toc-depth=2",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"built {docx.name}: {docx.stat().st_size // 1024} KB")
    else:
        print("pandoc failed:", result.stderr[:300])


if __name__ == "__main__":
    main()
