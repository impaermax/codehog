"""Bonus grants issued by an admin."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class BonusGrant(Base):
    """A bonus granted to every registered user at once.

    A user receives it on their next visit: we compare the id of the last
    grant they have received with this table. That way each grant is paid
    exactly once, even if the user was offline when it was issued.
    """

    __tablename__ = "bonus_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
