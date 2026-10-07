"""Game data: hedgehog skins, the user's collection and wheel spins."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utc_now

if TYPE_CHECKING:
    from app.models.user import User


class Slot(enum.StrEnum):
    """Where an item is worn.

    Every skin uses SKIN. The other values remain from the retired clothing
    catalog, whose rows are kept so that past purchases are not lost.
    """

    HEAD = "head"
    FACE = "face"
    BODY = "body"
    BACK = "back"
    SKIN = "skin"
    VEHICLE = "vehicle"
    HOME = "home"


class Item(Base):
    """A hedgehog skin, one of the 54 in the collection. Purely cosmetic."""

    __tablename__ = "items"
    __table_args__ = (CheckConstraint("price >= 0", name="ck_item_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    slot: Mapped[Slot] = mapped_column(
        Enum(Slot, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    # Image file name: static/img/skins/{asset_key}.webp
    asset_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # False means the item is no longer sold; existing purchases are kept.
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Collection tier: 1 is available right after sign-up, tier N unlocks
    # once module N-1 of the course is completed. 0 marks retired clothing.
    tier: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    owners: Mapped[list[UserItem]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class UserItem(Base):
    """The hedgehog collection: which skins a user owns and which one is active.

    The starter hedgehog chosen at sign-up is a regular row here, granted for
    free and active right away. There is no separate field for it.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),
        # A user has exactly one active hedgehog; the database enforces it.
        Index(
            "uq_inventory_one_active", "user_id", unique=True, sqlite_where=text("is_equipped = 1")
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    # The active hedgehog. At most one row per user can be true.
    is_equipped: Mapped[bool] = mapped_column(default=False, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="owners")


class WheelSpin(Base):
    """A single wheel spin. The milestone prevents paying the same prize twice."""

    __tablename__ = "wheel_spins"
    __table_args__ = (UniqueConstraint("user_id", "milestone", name="uq_spin_user_milestone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    milestone: Mapped[int] = mapped_column(Integer, nullable=False)  # number of the 5-lesson block
    sector_index: Mapped[int] = mapped_column(Integer, nullable=False)
    coins_won: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="spins")
