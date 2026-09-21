"""Массовые начисления от админа."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, сейчас


class BonusGrant(Base):
    """Бонус, начисленный всем сразу.

    Пользователь получает его при следующем заходе: сравниваем id последнего
    увиденного бонуса с этой таблицей. Так начисление происходит ровно один раз
    и работает, даже когда человек был офлайн.
    """

    __tablename__ = "bonus_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)
