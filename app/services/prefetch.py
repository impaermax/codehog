"""Фоновая подготовка уроков.

Генерация урока моделью занимает 15–25 секунд. Держать человека на загрузке
столько нельзя, поэтому:
  · первый урок наполняется шаблоном сразу — старт мгновенный;
  · следующие готовятся в фоне, пока человек занимается текущим.
Так ожидания не видно вообще, а качество модели подхватывается со второго урока.
"""
from __future__ import annotations

import logging
import threading

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Course, Lesson, TestAttempt, User

лог = logging.getLogger("codehog.prefetch")

БУФЕР = 3          # сколько уроков держать наготове
_занятые: set[int] = set()
_замок = threading.Lock()


def _подготовить(user_id: int, сколько: int) -> None:
    from app.services.course import ГенераторКурса
    from app.services.testbank import АдаптивныйТест

    сессия = SessionLocal()
    try:
        юзер = сессия.get(User, user_id)
        if юзер is None:
            return
        курс = сессия.scalar(
            select(Course).where(Course.user_id == user_id).order_by(Course.id.desc())
        )
        if курс is None:
            return

        попытка = сессия.scalar(
            select(TestAttempt).where(TestAttempt.user_id == user_id).order_by(TestAttempt.id.desc())
        )
        слабые = АдаптивныйТест.слабые_темы(попытка.ответы) if попытка else []

        генератор = ГенераторКурса(сессия)
        сделано = 0
        for урок in курс.все_уроки:
            if сделано >= сколько:
                break
            if урок.tasks:
                continue
            генератор.наполнить_урок(урок, юзер, слабые)
            сделано += 1
        if сделано:
            лог.info("фоном подготовлено уроков: %s (пользователь %s)", сделано, user_id)
    except Exception as e:  # фон не имеет права ронять приложение
        лог.warning("фоновая подготовка не удалась: %s", str(e)[:200])
    finally:
        сессия.close()
        with _замок:
            _занятые.discard(user_id)


def запустить(user_id: int, сколько: int = БУФЕР) -> bool:
    """Ставит подготовку в фон. Повторный вызов для того же человека игнорируется."""
    with _замок:
        if user_id in _занятые:
            return False
        _занятые.add(user_id)
    поток = threading.Thread(target=_подготовить, args=(user_id, сколько), daemon=True)
    поток.start()
    return True
