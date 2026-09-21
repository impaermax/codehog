"""Награды за поведение: медали и мемы.

Медали закрывают требование 3.5 и UC-7, мемы — требование 3.1 и UC-2.
Обе сущности задаются данными, а не кодом: их пополняют через каталог,
не трогая логику. Это и есть требование масштабируемости из блока 5.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, сейчас

if TYPE_CHECKING:
    from app.models.user import User


class ТипУсловия(str, enum.Enum):
    """За что выдаётся медаль. Значение считается на сервере в момент проверки."""

    ТЕСТ = "test_passed"        # пройден вводный тест
    УРОКИ = "lessons_done"      # решено N уроков
    СТРИК = "streak_days"       # серия из N дней подряд
    МОНЕТЫ = "coins_earned"     # заработано N монет за всё время
    ПРЕДМЕТЫ = "items_owned"    # куплено N предметов
    КОЛЕСО = "wheel_spins"      # колесо прокручено N раз
    БЕЗ_ОШИБОК = "flawless"     # N заданий решено с первой попытки

    @property
    def подпись(self) -> str:
        return {
            "test_passed": "Вводный тест",
            "lessons_done": "Пройдено уроков",
            "streak_days": "Дней подряд",
            "coins_earned": "Заработано монет",
            "items_owned": "Куплено предметов",
            "wheel_spins": "Вращений колеса",
            "flawless": "Решено с первой попытки",
        }[self.value]


class Achievement(Base):
    """Медаль: что за неё дают и при каком условии она выдаётся."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    icon: Mapped[str] = mapped_column(String(16), default="🏅", nullable=False)
    condition_type: Mapped[ТипУсловия] = mapped_column(
        Enum(ТипУсловия, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    holders: Mapped[list["UserAchievement"]] = relationship(
        back_populates="achievement", cascade="all, delete-orphan"
    )


class UserAchievement(Base):
    """Факт выдачи медали. Пара уникальна — одна медаль выдаётся ровно один раз."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), index=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=сейчас, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="achievements")
    achievement: Mapped["Achievement"] = relationship(back_populates="holders")


class Meme(Base):
    """Картинка, которую показывают после пройденного урока.

    Хранится ссылкой, а не файлом: подборку можно заменить целиком,
    не трогая код и не передеплоивая приложение.
    """

    __tablename__ = "memes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
