"""Общая база для всех моделей и переиспользуемые примеси."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def сейчас() -> datetime:
    """Время в UTC. Единая точка, чтобы не плодить naive-даты."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Общий предок всех таблиц."""

    def __repr__(self) -> str:  # удобнее отлаживать
        поля = ", ".join(
            f"{к}={getattr(self, к)!r}"
            for к in list(self.__mapper__.columns.keys())[:3]
        )
        return f"<{type(self).__name__} {поля}>"


class ВременнЫеМетки:
    """Примесь с датами создания и обновления."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=сейчас, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=сейчас, onupdate=сейчас, server_default=func.now(), nullable=False
    )
