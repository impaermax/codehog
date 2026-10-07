"""Declarative base shared by all models, plus reusable mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Current time in UTC. A single source, so no naive datetimes slip in."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Common ancestor of every table."""

    def __repr__(self) -> str:
        fields = ", ".join(
            f"{key}={getattr(self, key)!r}" for key in list(self.__mapper__.columns.keys())[:3]
        )
        return f"<{type(self).__name__} {fields}>"


class TimestampMixin:
    """Adds creation and update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
