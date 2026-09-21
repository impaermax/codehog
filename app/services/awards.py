"""Медали и мемы.

Закрывает требования 3.1 (мем после теста) и 3.5 (система достижений),
а также UC-2 и UC-7.

Правило выдачи одно: медаль выдаётся ровно один раз. Это гарантирует не
код, а уникальный индекс на паре (пользователь, медаль) — параллельные
запросы не смогут выдать дубль, как и в случае с колесом.
"""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    CoinTransaction,
    Lesson,
    Meme,
    Module,
    Course,
    Submission,
    TestAttempt,
    User,
    UserAchievement,
    UserItem,
    WheelSpin,
    ТипУсловия,
)

лог = logging.getLogger("codehog.awards")

# (код, название, описание, значок, условие, порог, порядок)
КАТАЛОГ_МЕДАЛЕЙ = [
    ("first_test",   "Первый шаг",     "Пройден вводный тест на уровень",        "🎯", ТипУсловия.ТЕСТ,        1,    10),
    ("first_lesson", "Начало положено", "Первый урок пройден полностью",          "🌱", ТипУсловия.УРОКИ,       1,    20),
    ("lessons_10",   "Десятка",        "Пройдено 10 уроков",                      "📚", ТипУсловия.УРОКИ,       10,   30),
    ("lessons_50",   "Полста",         "Пройдено 50 уроков",                      "🏛", ТипУсловия.УРОКИ,       50,   40),
    ("streak_7",     "Неделя огня",    "Семь дней занятий подряд",                "🔥", ТипУсловия.СТРИК,       7,    50),
    ("streak_30",    "Месяц огня",     "Тридцать дней занятий подряд",            "🌋", ТипУсловия.СТРИК,       30,   60),
    ("coins_100",    "Первая сотня",   "Заработано 100 монет за всё время",       "🪙", ТипУсловия.МОНЕТЫ,      100,  70),
    ("coins_1000",   "Тысячник",       "Заработано 1000 монет за всё время",      "💰", ТипУсловия.МОНЕТЫ,      1000, 80),
    ("items_3",      "Модник",         "Куплено три предмета",                    "🎩", ТипУсловия.ПРЕДМЕТЫ,    3,    90),
    ("wheel_5",      "Везунчик",       "Колесо прокручено пять раз",              "🎡", ТипУсловия.КОЛЕСО,      5,    100),
    ("flawless_5",   "Без осечек",     "Пять заданий решено с первой попытки",    "✨", ТипУсловия.БЕЗ_ОШИБОК,  5,    110),
]

# Мемы — данные, а не код. Подборку можно заменить целиком, не трогая логику.
КАТАЛОГ_МЕМОВ = [
    ("works_local", "/static/img/мемы/works-local.webp", "Работает на моей машине"),
    ("semicolon",   "/static/img/мемы/semicolon.webp",   "Три часа искал опечатку"),
    ("it_compiles", "/static/img/мемы/it-compiles.webp", "Заработало с первого раза. Подозрительно"),
    ("indent",      "/static/img/мемы/indent.webp",      "Python и отступы"),
    ("stack",       "/static/img/мемы/stack.webp",       "Скопировал со Stack Overflow"),
    ("off_by_one",  "/static/img/мемы/off-by-one.webp",  "Ошибка на единицу"),
]


def засеять_награды(сессия: Session) -> tuple[int, int]:
    """Добавляет недостающие медали и мемы. Повторный вызов безопасен."""
    медалей = мемов = 0
    for код, имя, описание, значок, условие, порог, порядок in КАТАЛОГ_МЕДАЛЕЙ:
        if сессия.scalar(select(Achievement).where(Achievement.code == код)):
            continue
        сессия.add(Achievement(
            code=код, title=имя, description=описание, icon=значок,
            condition_type=условие, target_value=порог, sort_order=порядок,
        ))
        медалей += 1
    for порядок, (код, ссылка, подпись) in enumerate(КАТАЛОГ_МЕМОВ, start=1):
        if сессия.scalar(select(Meme).where(Meme.code == код)):
            continue
        сессия.add(Meme(code=код, image_url=ссылка, caption=подпись, sort_order=порядок * 10))
        мемов += 1
    сессия.commit()
    return медалей, мемов


class Медали:
    """Считает текущие показатели ученика и выдаёт заслуженные медали."""

    def __init__(self, сессия: Session) -> None:
        self.сессия = сессия

    # --- измерения ---

    def _уроков_пройдено(self, юзер: User) -> int:
        return self.сессия.scalar(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .join(Course, Module.course_id == Course.id)
            .where(Course.user_id == юзер.id, Lesson.is_completed.is_(True))
        ) or 0

    def _монет_заработано(self, юзер: User) -> int:
        """Только приход. Покупки баланс уменьшают, но заслугу не отменяют."""
        return self.сессия.scalar(
            select(func.coalesce(func.sum(CoinTransaction.amount), 0))
            .where(CoinTransaction.user_id == юзер.id, CoinTransaction.amount > 0)
        ) or 0

    def _без_ошибок(self, юзер: User) -> int:
        """Задания, где единственная попытка оказалась верной."""
        по_заданию = (
            select(
                Submission.task_id.label("task_id"),
                func.count(Submission.id).label("всего"),
                func.sum(func.cast(Submission.passed, Integer)).label("верных"),
            )
            .where(Submission.user_id == юзер.id)
            .group_by(Submission.task_id)
            .subquery()
        )
        return self.сессия.scalar(
            select(func.count()).select_from(по_заданию)
            .where(по_заданию.c.всего == 1, по_заданию.c.верных == 1)
        ) or 0

    def показатели(self, юзер: User) -> dict[ТипУсловия, int]:
        сч = self.сессия.scalar
        return {
            ТипУсловия.ТЕСТ: сч(
                select(func.count(TestAttempt.id)).where(
                    TestAttempt.user_id == юзер.id, TestAttempt.determined_level.is_not(None)
                )
            ) or 0,
            ТипУсловия.УРОКИ: self._уроков_пройдено(юзер),
            ТипУсловия.СТРИК: юзер.streak_best,
            ТипУсловия.МОНЕТЫ: self._монет_заработано(юзер),
            ТипУсловия.ПРЕДМЕТЫ: сч(
                select(func.count(UserItem.id)).where(UserItem.user_id == юзер.id)
            ) or 0,
            ТипУсловия.КОЛЕСО: сч(
                select(func.count(WheelSpin.id)).where(WheelSpin.user_id == юзер.id)
            ) or 0,
            ТипУсловия.БЕЗ_ОШИБОК: self._без_ошибок(юзер),
        }

    # --- выдача ---

    def проверить(self, юзер: User) -> list[Achievement]:
        """Выдаёт все медали, условия которых уже выполнены. Возвращает новые."""
        уже = {
            строка.achievement_id
            for строка in self.сессия.scalars(
                select(UserAchievement).where(UserAchievement.user_id == юзер.id)
            )
        }
        значения = self.показатели(юзер)
        новые: list[Achievement] = []
        for медаль in self.сессия.scalars(select(Achievement).order_by(Achievement.sort_order)):
            if медаль.id in уже:
                continue
            if значения.get(медаль.condition_type, 0) < медаль.target_value:
                continue
            self.сессия.add(UserAchievement(user_id=юзер.id, achievement_id=медаль.id))
            try:
                self.сессия.flush()
            except IntegrityError:
                # параллельный запрос успел раньше — это нормально, медаль уже есть
                self.сессия.rollback()
                continue
            новые.append(медаль)
        if новые:
            self.сессия.commit()
            лог.info("медали выданы %s: %s", юзер.username, [м.code for м in новые])
        return новые

    def все_с_отметкой(self, юзер: User) -> list[tuple[Achievement, bool, int]]:
        """Весь каталог с признаком «получена» и текущим прогрессом — для профиля."""
        полученные = {
            с.achievement_id: с
            for с in self.сессия.scalars(
                select(UserAchievement).where(UserAchievement.user_id == юзер.id)
            )
        }
        значения = self.показатели(юзер)
        итог = []
        for медаль in self.сессия.scalars(select(Achievement).order_by(Achievement.sort_order)):
            текущее = значения.get(медаль.condition_type, 0)
            итог.append((медаль, медаль.id in полученные, min(текущее, медаль.target_value)))
        return итог


def случайный_мем(сессия: Session) -> Meme | None:
    """Мем после пройденного урока. Выбор на сервере, как и приз колеса."""
    мемы = list(сессия.scalars(select(Meme).where(Meme.is_active.is_(True))))
    return мемы[secrets.randbelow(len(мемы))] if мемы else None
