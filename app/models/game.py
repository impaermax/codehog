"""Игровая часть: скины ежа, коллекция пользователя и вращения колеса."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, сейчас

if TYPE_CHECKING:
    from app.models.user import User


class Слот(str, enum.Enum):
    """Куда надевается предмет. В одном слоте одновременно только одна вещь."""

    ГОЛОВА = "head"
    ЛИЦО = "face"
    ТЕЛО = "body"
    СПИНА = "back"
    СКИН = "skin"
    ТРАНСПОРТ = "vehicle"
    ДОМ = "home"

    @property
    def подпись(self) -> str:
        return {
            "head": "Голова", "face": "Лицо", "body": "Одежда", "back": "Спина",
            "skin": "Скин", "vehicle": "Транспорт", "home": "Дом",
        }[self.value]


class Item(Base):
    """Скин ежа — один из 54 в коллекции. Меняет только вид, преимуществ в обучении не даёт."""

    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_item_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False,
                                     comment="Код скина: hog-{уровень}-{номер}")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    slot: Mapped[Слот] = mapped_column(
        Enum(Слот, values_callable=lambda e: [x.value for x in e]), nullable=False,
        comment="Для скинов всегда skin. Другие значения — от старого каталога одежды",
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False, comment="Цена в монетах")
    asset_key: Mapped[str] = mapped_column(String(64), nullable=False,
                                           comment="Имя картинки: static/img/skins/{asset_key}.webp")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False,
                                            comment="false — снят с продажи, покупки сохраняются")
    # Уровень скина: 1 — доступен с регистрации, 2–6 открываются после
    # прохождения 1–5 модулей курса. 0 — не скин (старая одежда).
    tier: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Уровень коллекции 1–6: уровень N открывается после модуля N−1. 0 — старая одежда",
    )

    owners: Mapped[list["UserItem"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class UserItem(Base):
    """Коллекция ежей: какие скины есть у пользователя и какой из них активный.

    Стартовый ёж, выбранный при регистрации, — обычная запись здесь же,
    выданная бесплатно и сразу активная. Отдельного поля для него нет.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),
        # активный ёж у пользователя один: правило держит база, а не только код
        Index("uq_inventory_one_active", "user_id", unique=True,
              sqlite_where=text("is_equipped = 1")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    is_equipped: Mapped[bool] = mapped_column(
        default=False, nullable=False,
        comment="Активный ёж. У пользователя не больше одной записи с true",
    )
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)

    user: Mapped["User"] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship(back_populates="owners")


class WheelSpin(Base):
    """Одно вращение колеса. milestone защищает от повторной выдачи приза."""

    __tablename__ = "wheel_spins"
    __table_args__ = (UniqueConstraint("user_id", "milestone", name="uq_spin_user_milestone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    milestone: Mapped[int] = mapped_column(Integer, nullable=False)  # номер пятёрки уроков
    sector_index: Mapped[int] = mapped_column(Integer, nullable=False)
    coins_won: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)

    user: Mapped["User"] = relationship(back_populates="spins")
