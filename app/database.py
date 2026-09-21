"""Подключение к базе и выдача сессий."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_путь = settings.database_url
if _путь.startswith("sqlite:///"):
    Path(_путь.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def получить_сессию() -> Iterator[Session]:
    """Зависимость FastAPI: сессия на запрос."""
    сессия = SessionLocal()
    try:
        yield сессия
    finally:
        сессия.close()


def создать_таблицы() -> None:
    from app.models import Base  # импорт здесь, чтобы все модели зарегистрировались

    Base.metadata.create_all(engine)
