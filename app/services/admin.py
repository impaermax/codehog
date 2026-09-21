"""Админские операции: аналитика, массовые бонусы, сброс прогресса."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BonusGrant,
    CoinTransaction,
    Course,
    Lesson,
    Submission,
    TestAttempt,
    User,
    UserItem,
    WheelSpin,
    ПричинаМонет,
    Уровень,
)
from app.services.auth import Аутентификация


@dataclass
class СтрокаПользователя:
    """Одна строка таблицы пользователей в панели."""

    id: int
    username: str
    email: str
    уровень: str
    этап: str
    уроков: int
    всего_уроков: int
    монет: int
    стрик: int
    предметов: int
    последняя_активность: str


@dataclass
class Аналитика:
    """Сводка по продукту."""

    всего: int = 0
    активны_сегодня: int = 0
    активны_за_неделю: int = 0
    тестов_пройдено: int = 0
    зарегистрировались_после_теста: int = 0
    начали_курс: int = 0
    завершили_первый_урок: int = 0
    попыток_кода: int = 0
    доля_успешных: float = 0.0
    монет_выдано: int = 0
    монет_потрачено: int = 0
    вращений: int = 0
    по_уровням: dict = field(default_factory=dict)
    пользователи: list = field(default_factory=list)

    @property
    def конверсия_в_регистрацию(self) -> float:
        return self.зарегистрировались_после_теста * 100 / self.тестов_пройдено if self.тестов_пройдено else 0.0

    @property
    def конверсия_в_первый_урок(self) -> float:
        return self.завершили_первый_урок * 100 / self.всего if self.всего else 0.0


class Админка:
    """Всё, что делает администратор."""

    ЛОГИН = "maks-admin"

    def __init__(self, сессия: Session) -> None:
        self.сессия = сессия

    # --- учётная запись ---

    def создать_админа(self, пароль: str, email: str = "maks-admin@codehog.local") -> User | None:
        """Заводит админа, если его ещё нет. Пароль берётся из ADMIN_PASSWORD."""
        существующий = self.сессия.scalar(select(User).where(User.username == self.ЛОГИН))
        if существующий:
            if not существующий.is_admin:
                существующий.is_admin = True
                self.сессия.commit()
            return существующий
        юзер = User(
            email=email, username=self.ЛОГИН,
            password_hash=Аутентификация.хеш(пароль),
            level=Уровень.ПРОДВИНУТЫЙ, is_admin=True, coins=1_000_000,
        )
        self.сессия.add(юзер)
        self.сессия.commit()
        return юзер

    # --- аналитика ---

    def собрать(self) -> Аналитика:
        с = self.сессия
        сегодня = date.today()
        неделя = сегодня - timedelta(days=7)
        итог = Аналитика()

        итог.всего = с.query(User).count()
        итог.активны_сегодня = с.query(User).filter(User.last_active_on == сегодня).count()
        итог.активны_за_неделю = с.query(User).filter(User.last_active_on >= неделя).count()
        итог.тестов_пройдено = с.query(TestAttempt).count()
        итог.зарегистрировались_после_теста = (
            с.query(TestAttempt).filter(TestAttempt.user_id.isnot(None)).count()
        )
        итог.начали_курс = с.query(Course).count()
        итог.завершили_первый_урок = (
            с.query(func.count(func.distinct(Lesson.id)))
            .select_from(Lesson).filter(Lesson.is_completed.is_(True)).scalar() or 0
        )

        попытки = с.query(Submission).count()
        успешных = с.query(Submission).filter(Submission.passed.is_(True)).count()
        итог.попыток_кода = попытки
        итог.доля_успешных = успешных * 100 / попытки if попытки else 0.0

        итог.монет_выдано = с.query(func.coalesce(func.sum(CoinTransaction.amount), 0)).filter(
            CoinTransaction.amount > 0
        ).scalar() or 0
        итог.монет_потрачено = abs(с.query(func.coalesce(func.sum(CoinTransaction.amount), 0)).filter(
            CoinTransaction.amount < 0
        ).scalar() or 0)
        итог.вращений = с.query(WheelSpin).count()

        счётчик = Counter(u.level.подпись for u in с.query(User).all())
        итог.по_уровням = dict(счётчик)
        итог.пользователи = self._строки()
        return итог

    def _строки(self) -> list[СтрокаПользователя]:
        строки = []
        for u in self.сессия.query(User).order_by(User.id.desc()).limit(200).all():
            курс = self.сессия.scalar(
                select(Course).where(Course.user_id == u.id).order_by(Course.id.desc())
            )
            уроки = курс.все_уроки if курс else []
            готово = sum(1 for л in уроки if л.is_completed)
            предметов = self.сессия.query(UserItem).filter(UserItem.user_id == u.id).count()
            строки.append(СтрокаПользователя(
                id=u.id, username=u.username, email=u.email,
                уровень=u.level.подпись, этап=self._этап(курс, готово, len(уроки)),
                уроков=готово, всего_уроков=len(уроки), монет=u.coins,
                стрик=u.streak_current, предметов=предметов,
                последняя_активность=u.last_active_on.isoformat() if u.last_active_on else "—",
            ))
        return строки

    @staticmethod
    def _этап(курс, готово: int, всего: int) -> str:
        if курс is None:
            return "нет курса"
        if готово == 0:
            return "зарегистрировался"
        if всего and готово >= всего:
            return "курс пройден"
        if готово < 3:
            return "первые уроки"
        return "в процессе"

    # --- бонусы ---

    def начислить_всем(self, сумма: int, комментарий: str, автор: str = "admin") -> BonusGrant:
        """Записывает бонус. Деньги упадут каждому при следующем заходе."""
        бонус = BonusGrant(amount=сумма, comment=комментарий, created_by=автор)
        self.сессия.add(бонус)
        self.сессия.commit()
        return бонус

    def выдать_ожидающие(self, юзер: User) -> list[BonusGrant]:
        """Начисляет всё, что человек ещё не получил. Вызывается на каждой странице."""
        новые = self.сессия.scalars(
            select(BonusGrant).where(BonusGrant.id > юзер.last_bonus_id).order_by(BonusGrant.id)
        ).all()
        if not новые:
            return []
        for бонус in новые:
            юзер.coins += бонус.amount
            self.сессия.add(CoinTransaction(
                user_id=юзер.id, amount=бонус.amount, reason=ПричинаМонет.СТРИК,
                comment=f"бонус: {бонус.comment}"[:255], balance_after=юзер.coins,
            ))
            юзер.last_bonus_id = бонус.id
        self.сессия.commit()
        return list(новые)

    # --- сброс ---

    def сбросить(self, юзер: User) -> None:
        """Обнуляет прогресс: курс, монеты, инвентарь, стрик, попытки."""
        с = self.сессия
        с.query(Submission).filter(Submission.user_id == юзер.id).delete(synchronize_session=False)
        с.query(UserItem).filter(UserItem.user_id == юзер.id).delete(synchronize_session=False)
        с.query(WheelSpin).filter(WheelSpin.user_id == юзер.id).delete(synchronize_session=False)
        с.query(CoinTransaction).filter(CoinTransaction.user_id == юзер.id).delete(synchronize_session=False)
        for курс in с.query(Course).filter(Course.user_id == юзер.id).all():
            с.delete(курс)
        юзер.coins = 1_000_000 if юзер.is_admin else 0
        юзер.xp = 0
        юзер.streak_current = 0
        юзер.streak_best = 0
        юзер.last_active_on = None
        юзер.lessons_since_wheel = 0
        с.commit()
