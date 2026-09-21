#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Убирает фон у персонажа заливкой от краёв.

Обычный colorkey убирает ВСЕ пиксели похожего цвета — вместе с чёрным худи,
которое почти совпадает с фоном. Заливка от краёв трогает только тот фон,
который связан с рамкой кадра, поэтому одежда остаётся целой.

    python3 убрать-фон.py ../app/static/img/hog-base.png img/hog-base.png
"""
from __future__ import annotations

import sys
from collections import deque

from PIL import Image

ДОПУСК = 42          # насколько цвет может отличаться от фонового
РАЗМЫТИЕ_КРАЯ = 1    # смягчение границы, пикселей


def похоже(a: tuple[int, int, int], b: tuple[int, int, int], допуск: int) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) <= допуск * 3


def убрать(вход: str, выход: str, допуск: int = ДОПУСК) -> None:
    картинка = Image.open(вход).convert("RGBA")
    ш, в = картинка.size
    пиксели = картинка.load()
    фон = пиксели[0, 0][:3]

    посещено = bytearray(ш * в)
    очередь: deque[tuple[int, int]] = deque()

    # стартуем со всех точек рамки
    for x in range(ш):
        очередь.append((x, 0))
        очередь.append((x, в - 1))
    for y in range(в):
        очередь.append((0, y))
        очередь.append((ш - 1, y))

    убрано = 0
    while очередь:
        x, y = очередь.popleft()
        if not (0 <= x < ш and 0 <= y < в):
            continue
        индекс = y * ш + x
        if посещено[индекс]:
            continue
        цвет = пиксели[x, y]
        if not похоже(цвет[:3], фон, допуск):
            continue
        посещено[индекс] = 1
        пиксели[x, y] = (цвет[0], цвет[1], цвет[2], 0)
        убрано += 1
        очередь.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    картинка.save(выход)
    доля = убрано * 100 // (ш * в)
    print(f"{выход}: удалено {доля}% кадра ({убрано} пикселей)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("нужны путь-источник и путь-результат")
    убрать(sys.argv[1], sys.argv[2])
