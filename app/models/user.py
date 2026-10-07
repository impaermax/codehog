"""Пользователь, его дневная активность и движение монет."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ВременнЫеМетки, сейчас

if TYPE_CHECKING:
    from app.models.game import UserItem, WheelSpin
    from app.models.learning import Course, Submission, TestAttempt


class Уровень(str, enum.Enum):
    """Уровень владения Python, который определяет входной тест."""

    НОВИЧОК = "beginner"
    СРЕДНИЙ = "intermediate"
    ПРОДВИНУТЫЙ = "advanced"

    @property
    def подпись(self) -> str:
        return {"beginner": "Новичок", "intermediate": "Средний", "advanced": "Продвинутый"}[self.value]


class ПричинаМонет(str, enum.Enum):
    """Откуда пришли или куда ушли монеты. Нужна для честной истории баланса."""

    УРОК = "lesson"
    СТРИК = "streak"
    КОЛЕСО = "wheel"
    ТЕСТ = "test"
    ПОКУПКА = "purchase"
    БОНУС = "bonus"         # подарок от команды из админки
    ВОЗВРАТ = "refund"


class User(Base, ВременнЫеМетки):
    """Ученик. Хранит и профиль, и игровой баланс, и состояние стрика."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    level: Mapped[Уровень] = mapped_column(
        Enum(Уровень, values_callable=lambda e: [x.value for x in e]),
        default=Уровень.НОВИЧОК,
        nullable=False,
    )
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    streak_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_best: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    lessons_since_wheel: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # админ: безлимитный баланс, доступ к панели и раздаче бонусов
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    # последний увиденный бонус — чтобы показать уведомление один раз
    last_bonus_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    courses: Mapped[list["Course"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    test_attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    items: Mapped[list["UserItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    spins: Mapped[list["WheelSpin"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    achievements: Mapped[list["UserAchievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["CoinTransaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="CoinTransaction.id.desc()"
    )
    activity: Mapped[list["DailyActivity"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def безлимит(self) -> bool:
        """У админа монеты не тратятся — удобно проверять магазин."""
        return self.is_admin

    @property
    def показать_баланс(self) -> str:
        return "∞" if self.is_admin else str(self.coins)

    @property
    def ранг(self) -> int:
        """Игровой ранг из опыта: каждые 100 XP — плюс ранг."""
        return self.xp // 100 + 1


class DailyActivity(Base):
    """Один день занятий. На этой таблице живёт трекер и календарь."""

    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lessons_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_reward_given: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="activity")


class CoinTransaction(Base):
    """Каждое движение монет. Баланс всегда можно пересчитать по истории."""

    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # отрицательное = трата
    reason: Mapped[ПричинаМонет] = mapped_column(
        Enum(ПричинаМонет, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)

    user: Mapped["User"] = relationship(back_populates="transactions")
