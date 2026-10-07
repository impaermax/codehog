"""Behaviour rewards: medals and memes.

Medals cover requirement 3.5 and UC-7, memes cover requirement 3.1 and UC-2.
Both are defined by data rather than code: new ones are added to the catalog
without touching the logic.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utc_now

if TYPE_CHECKING:
    from app.models.user import User


class ConditionType(enum.StrEnum):
    """What a medal is awarded for. The value is computed on the server when checked."""

    TEST = "test_passed"  # placement test completed
    LESSONS = "lessons_done"  # N lessons completed
    STREAK = "streak_days"  # N days in a row
    COINS = "coins_earned"  # N coins earned in total
    ITEMS = "items_owned"  # N skins in the collection
    WHEEL = "wheel_spins"  # wheel spun N times
    FLAWLESS = "flawless"  # N tasks solved on the first attempt


class Achievement(Base):
    """A medal: what it is called and under which condition it is awarded."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(16), default="🏅", nullable=False)
    condition_type: Mapped[ConditionType] = mapped_column(
        Enum(ConditionType, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    holders: Mapped[list[UserAchievement]] = relationship(
        back_populates="achievement", cascade="all, delete-orphan"
    )


class UserAchievement(Base):
    """A medal awarded to a user. The pair is unique, so a medal is awarded only once."""

    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), index=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="achievements")
    achievement: Mapped[Achievement] = relationship(back_populates="holders")


class Meme(Base):
    """An image shown after a completed lesson.

    Stored as a URL rather than a file, so the whole set can be replaced
    without changing code.
    """

    __tablename__ = "memes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
