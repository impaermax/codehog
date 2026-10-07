"""Users, their daily activity and coin movements."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.game import UserItem, WheelSpin
    from app.models.learning import Course, Submission, TestAttempt
    from app.models.reward import UserAchievement


class Level(enum.StrEnum):
    """Python skill level, determined by the placement test."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def label(self) -> str:
        """Name shown in the UI."""
        return {"beginner": "Новичок", "intermediate": "Средний", "advanced": "Продвинутый"}[
            self.value
        ]


class CoinReason(enum.StrEnum):
    """Where coins came from or went to. Keeps the balance history honest."""

    LESSON = "lesson"
    STREAK = "streak"
    WHEEL = "wheel"
    TEST = "test"
    PURCHASE = "purchase"
    BONUS = "bonus"  # a gift from the team, granted in the admin panel
    REFUND = "refund"


class User(Base, TimestampMixin):
    """A learner: profile, game balance and streak state."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    level: Mapped[Level] = mapped_column(
        Enum(Level, values_callable=lambda e: [x.value for x in e]),
        default=Level.BEGINNER,
        nullable=False,
    )
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    streak_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_best: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    lessons_since_wheel: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Admins have an unlimited balance and access to the admin panel.
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    # The last bonus grant the user has received, so each grant is paid once.
    last_bonus_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    courses: Mapped[list[Course]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    test_attempts: Mapped[list[TestAttempt]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    items: Mapped[list[UserItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    spins: Mapped[list[WheelSpin]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[list[UserAchievement]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[CoinTransaction]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="CoinTransaction.id.desc()"
    )
    activity: Mapped[list[DailyActivity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def balance_display(self) -> str:
        """Balance as shown in the UI: admins see an infinity sign."""
        return "∞" if self.is_admin else str(self.coins)

    @property
    def rank(self) -> int:
        """Game rank derived from XP: one rank per 100 XP."""
        return self.xp // 100 + 1


class DailyActivity(Base):
    """One day of study. The streak tracker is built on this table."""

    __tablename__ = "daily_activity"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_activity_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lessons_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_reward_given: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="activity")


class CoinTransaction(Base):
    """A single coin movement. The balance can always be rebuilt from this history."""

    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # negative means spending
    reason: Mapped[CoinReason] = mapped_column(
        Enum(CoinReason, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="transactions")
