"""Точка входа: собирает приложение, поднимает базу и раздаёт статику."""
from __future__ import annotations

import fcntl
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import actions, admin, pages
from app.api.admin import НужнаАвторизация
from app.config import settings
from app.database import SessionLocal, engine, создать_таблицы
from app.services.admin import Админка
from app.services.migrate import дополнить_схему
from app.services.awards import засеять_награды
from app.services.seed import засеять_каталог

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
лог = logging.getLogger("codehog")

приложение = FastAPI(title="CodeHogwarts", version=__version__, docs_url=f"{settings.base_path}/hog/docs")
БАЗА = settings.base_path          # "" или "/codehog"
приложение.mount(f"{БАЗА}/static", StaticFiles(directory="app/static"), name="static")
# Все маршруты живут внутри БАЗЫ: при BASE_PATH=codehog приложение
# целиком открывается по https://maks.my/codehog
приложение.include_router(pages.роутер, prefix=БАЗА)
приложение.include_router(actions.роутер, prefix=БАЗА)
приложение.include_router(admin.роутер, prefix=БАЗА)


@приложение.on_event("startup")
def подготовить() -> None:
    """Инициализация базы.

    Воркеров несколько, и без блокировки они одновременно создают таблицы —
    один падает с «table already exists». Поэтому инициализацию выполняет
    ровно один процесс, остальные ждут и идут дальше.
    """
    замок = Path(tempfile.gettempdir()) / "codehog-init.lock"
    with замок.open("w") as ф:
        fcntl.flock(ф, fcntl.LOCK_EX)
        try:
            создать_таблицы()
            дополнить_схему(engine)
            сессия = SessionLocal()
            try:
                добавлено = засеять_каталог(сессия)
                медалей, мемов = засеять_награды(сессия)
                админ = Админка(сессия).создать_админа(settings.admin_password)
                лог.info("Админ: %s / пароль из ADMIN_PASSWORD", админ.username)
                лог.info("Медалей добавлено: %s, мемов: %s", медалей, мемов)
            finally:
                сессия.close()
        finally:
            fcntl.flock(ф, fcntl.LOCK_UN)
    лог.info("CodeHogwarts %s готов. Предметов добавлено: %s", __version__, добавлено)
    лог.info("Модель курсов: %s (ключ %s)", settings.course_model,
             "задан" if settings.ai_включён else "не задан — работают шаблоны")


@приложение.exception_handler(НужнаАвторизация)
def _на_вход(request, exc):  # noqa: ARG001
    return RedirectResponse(f"{БАЗА}/login?next={БАЗА}/admin", status_code=303)


@приложение.get(f"{БАЗА}/health")
def здоровье() -> dict:
    return {"status": "ok", "version": __version__, "ai": settings.ai_включён}
