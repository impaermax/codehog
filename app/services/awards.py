"""Medals and memes.

Covers requirements 3.1 (a meme after a lesson) and 3.5 (achievements),
as well as UC-2 and UC-7.

A medal is awarded exactly once. That is guaranteed not by code but by a
unique index on the (user, medal) pair: parallel requests cannot award a
duplicate, just like with the wheel.
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
    ConditionType,
    Course,
    Lesson,
    Meme,
    Module,
    Submission,
    TestAttempt,
    User,
    UserAchievement,
    UserItem,
    WheelSpin,
)

logger = logging.getLogger("codehog.awards")

# (code, title, description, icon, condition, threshold, sort order)
MEDAL_CATALOG = [
    (
        "first_test",
        "Первый шаг",
        "Пройден вводный тест на уровень",
        "🎯",
        ConditionType.TEST,
        1,
        10,
    ),
    (
        "first_lesson",
        "Начало положено",
        "Первый урок пройден полностью",
        "🌱",
        ConditionType.LESSONS,
        1,
        20,
    ),
    ("lessons_10", "Десятка", "Пройдено 10 уроков", "📚", ConditionType.LESSONS, 10, 30),
    ("lessons_50", "Полста", "Пройдено 50 уроков", "🏛", ConditionType.LESSONS, 50, 40),
    ("streak_7", "Неделя огня", "Семь дней занятий подряд", "🔥", ConditionType.STREAK, 7, 50),
    (
        "streak_30",
        "Месяц огня",
        "Тридцать дней занятий подряд",
        "🌋",
        ConditionType.STREAK,
        30,
        60,
    ),
    (
        "coins_100",
        "Первая сотня",
        "Заработано 100 монет за всё время",
        "🪙",
        ConditionType.COINS,
        100,
        70,
    ),
    (
        "coins_1000",
        "Тысячник",
        "Заработано 1000 монет за всё время",
        "💰",
        ConditionType.COINS,
        1000,
        80,
    ),
    ("items_3", "Модник", "В коллекции три ежа", "🎩", ConditionType.ITEMS, 3, 90),
    ("wheel_5", "Везунчик", "Колесо прокручено пять раз", "🎡", ConditionType.WHEEL, 5, 100),
    (
        "flawless_5",
        "Без осечек",
        "Пять заданий решено с первой попытки",
        "✨",
        ConditionType.FLAWLESS,
        5,
        110,
    ),
]  # noqa: E501

# Memes are data, not code: the whole set can be replaced without touching the logic.
MEME_CATALOG = [
    ("works_local", "/static/img/memes/works-local.webp", "Работает на моей машине"),
    ("semicolon", "/static/img/memes/semicolon.webp", "Три часа искал опечатку"),
    (
        "it_compiles",
        "/static/img/memes/it-compiles.webp",
        "Заработало с первого раза. Подозрительно",
    ),
    ("indent", "/static/img/memes/indent.webp", "Python и отступы"),
    ("stack", "/static/img/memes/stack.webp", "Скопировал со Stack Overflow"),
    ("off_by_one", "/static/img/memes/off-by-one.webp", "Ошибка на единицу"),
]


def seed_rewards(session: Session) -> tuple[int, int]:
    """Add missing medals and memes. Safe to call repeatedly.

    Existing medals and memes are synced with the catalog (texts and image
    URL), so an edit in code reaches the database on the next start.
    Returns the number of medals and memes added.
    """
    medals_added = memes_added = 0
    for code, title, description, icon, condition, threshold, order in MEDAL_CATALOG:
        medal = session.scalar(select(Achievement).where(Achievement.code == code))
        if medal is not None:
            medal.title, medal.description, medal.icon = title, description, icon
            continue
        session.add(
            Achievement(
                code=code,
                title=title,
                description=description,
                icon=icon,
                condition_type=condition,
                target_value=threshold,
                sort_order=order,
            )
        )
        medals_added += 1
    for order, (code, url, caption) in enumerate(MEME_CATALOG, start=1):
        meme = session.scalar(select(Meme).where(Meme.code == code))
        if meme is not None:
            meme.image_url = url
            continue
        session.add(Meme(code=code, image_url=url, caption=caption, sort_order=order * 10))
        memes_added += 1
    session.commit()
    return medals_added, memes_added


class MedalService:
    """Measures a learner's progress and awards the medals they have earned."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- metrics ---

    def _lessons_completed(self, user: User) -> int:
        return (
            self.session.scalar(
                select(func.count(Lesson.id))
                .join(Module, Lesson.module_id == Module.id)
                .join(Course, Module.course_id == Course.id)
                .where(Course.user_id == user.id, Lesson.is_completed.is_(True))
            )
            or 0
        )

    def _coins_earned(self, user: User) -> int:
        """Income only. Purchases lower the balance but do not cancel the achievement."""
        return (
            self.session.scalar(
                select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
                    CoinTransaction.user_id == user.id, CoinTransaction.amount > 0
                )
            )
            or 0
        )

    def _flawless_tasks(self, user: User) -> int:
        """Tasks whose only attempt was correct."""
        by_task = (
            select(
                Submission.task_id.label("task_id"),
                func.count(Submission.id).label("attempts"),
                func.sum(func.cast(Submission.passed, Integer)).label("passed"),
            )
            .where(Submission.user_id == user.id)
            .group_by(Submission.task_id)
            .subquery()
        )
        return (
            self.session.scalar(
                select(func.count())
                .select_from(by_task)
                .where(by_task.c.attempts == 1, by_task.c.passed == 1)
            )
            or 0
        )

    def metrics(self, user: User) -> dict[ConditionType, int]:
        """The learner's current value for every medal condition."""
        count = self.session.scalar
        return {
            ConditionType.TEST: count(
                select(func.count(TestAttempt.id)).where(
                    TestAttempt.user_id == user.id, TestAttempt.determined_level.is_not(None)
                )
            )
            or 0,
            ConditionType.LESSONS: self._lessons_completed(user),
            ConditionType.STREAK: user.streak_best,
            ConditionType.COINS: self._coins_earned(user),
            ConditionType.ITEMS: count(
                select(func.count(UserItem.id)).where(UserItem.user_id == user.id)
            )
            or 0,
            ConditionType.WHEEL: count(
                select(func.count(WheelSpin.id)).where(WheelSpin.user_id == user.id)
            )
            or 0,
            ConditionType.FLAWLESS: self._flawless_tasks(user),
        }

    # --- awarding ---

    def check(self, user: User) -> list[Achievement]:
        """Award every medal whose condition is already met. Returns the new ones."""
        already = {
            row.achievement_id
            for row in self.session.scalars(
                select(UserAchievement).where(UserAchievement.user_id == user.id)
            )
        }
        values = self.metrics(user)
        new_medals: list[Achievement] = []
        for medal in self.session.scalars(select(Achievement).order_by(Achievement.sort_order)):
            if medal.id in already:
                continue
            if values.get(medal.condition_type, 0) < medal.target_value:
                continue
            self.session.add(UserAchievement(user_id=user.id, achievement_id=medal.id))
            try:
                self.session.flush()
            except IntegrityError:
                # A parallel request got there first; the medal is already awarded.
                self.session.rollback()
                continue
            new_medals.append(medal)
        if new_medals:
            self.session.commit()
            logger.info(
                "medals awarded to %s: %s", user.username, [medal.code for medal in new_medals]
            )
        return new_medals

    def all_with_status(self, user: User) -> list[tuple[Achievement, bool, int]]:
        """The whole catalog with an "earned" flag and current progress, for the profile."""
        earned = {
            row.achievement_id
            for row in self.session.scalars(
                select(UserAchievement).where(UserAchievement.user_id == user.id)
            )
        }
        values = self.metrics(user)
        result = []
        for medal in self.session.scalars(select(Achievement).order_by(Achievement.sort_order)):
            current = values.get(medal.condition_type, 0)
            result.append((medal, medal.id in earned, min(current, medal.target_value)))
        return result


def random_meme(session: Session) -> Meme | None:
    """A meme for a completed lesson. Picked on the server, like the wheel prize."""
    memes = list(session.scalars(select(Meme).where(Meme.is_active.is_(True))))
    return memes[secrets.randbelow(len(memes))] if memes else None
