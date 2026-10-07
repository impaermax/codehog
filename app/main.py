"""Точка входа: собирает приложение, поднимает базу и раздаёт статику."""
from __future__ import annotations

import fcntl
import logging
import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import actions, admin, pages
from app.api.admin import НужнаАвторизация
from app.api.schemas import HealthOut
from app.config import settings
from app.database import SessionLocal, engine, создать_таблицы
from app.services.admin import Админка
from app.services.auth import COOKIE, Аутентификация
from app.services.migrate import дополнить_схему
from app.services.awards import засеять_награды
from app.services.seed import засеять_каталог

# Журнал сервера: время, уровень (INFO, WARNING, ERROR, CRITICAL), источник, сообщение.
# Под systemd всё уходит в системный журнал: journalctl -u codehog
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
лог = logging.getLogger("codehog")


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


@asynccontextmanager
async def жизненный_цикл(_: FastAPI):
    """Что делать при старте и остановке сервера (lifespan — замена устаревшего on_event)."""
    подготовить()
    yield


БАЗА = settings.base_path          # "" или "/codehog"


def _id_операции(маршрут: APIRoute) -> str:
    """operationId для OpenAPI: метод и путь латиницей, например post_hog_shop_buy_sku.

    По умолчанию FastAPI берёт имя функции, а оно у нас кириллическое и в
    схеме превращается в подчёркивания.
    """
    путь = маршрут.path_format.removeprefix(БАЗА)
    метод = sorted(маршрут.methods)[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", f"{метод}_{путь}").strip("_")


приложение = FastAPI(
    title="CodeHogwarts",
    version=__version__,
    description="Тренажёр Python. JSON-API для страниц сайта живёт под /hog.",
    lifespan=жизненный_цикл,
    # документация и схема — тоже внутри подкаталога, иначе на maks.my
    # Swagger запросит /openapi.json у соседнего сайта
    docs_url=f"{БАЗА}/hog/docs",
    redoc_url=None,
    openapi_url=f"{БАЗА}/hog/openapi.json",
    generate_unique_id_function=_id_операции,
)
приложение.mount(f"{БАЗА}/static", StaticFiles(directory="app/static"), name="static")
# Все маршруты живут внутри БАЗЫ: при BASE_PATH=codehog приложение
# целиком открывается по https://maks.my/codehog
приложение.include_router(pages.роутер, prefix=БАЗА, tags=["страницы"])
приложение.include_router(actions.роутер, prefix=БАЗА)
приложение.include_router(admin.роутер, prefix=БАЗА, tags=["админка"])


@приложение.middleware("http")
async def журнал_ошибок(request: Request, call_next):
    """Любое необработанное падение — в журнал, пользователю — понятный ответ.

    В журнал пишется метод и адрес запроса, ID пользователя (или «гость»)
    и полный стек ошибки, чтобы сбой можно было найти и воспроизвести.
    Наружу стек не уходит: JSON-запросы получают {"detail": "..."} с кодом 500,
    страницы — короткое сообщение.
    """
    try:
        return await call_next(request)
    except Exception:
        uid = Аутентификация.прочитать(request.cookies.get(COOKIE))
        лог.exception("сбой %s %s · пользователь %s",
                      request.method, request.url.path, uid if uid else "гость")
        if "/hog/" in request.url.path:
            return JSONResponse(
                {"detail": "Сервер не справился с запросом. Попробуйте ещё раз."},
                status_code=500,
            )
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>Ошибка</title>"
            "<body style='font-family:sans-serif;background:#101619;color:#F2F5EF;"
            "display:grid;place-items:center;height:100vh;margin:0'>"
            "<div style='text-align:center'><h1>Что-то пошло не так</h1>"
            "<p>Ошибка записана, мы её разберём. Обновите страницу.</p></div>",
            status_code=500,
        )


@приложение.exception_handler(RequestValidationError)
def _неверный_запрос(request: Request, exc: RequestValidationError):
    """Тело запроса не прошло схему: в журнал — подробности, пользователю — одна строка.

    Стандартный ответ FastAPI — список ошибок по полям. Фронтенд показывает
    detail как текст, поэтому отдаём его строкой, а разбор оставляем в журнале.
    """
    лог.warning("неверный запрос %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse({"detail": "Сервер не понял запрос. Обновите страницу и попробуйте снова."},
                        status_code=422)


@приложение.exception_handler(НужнаАвторизация)
def _на_вход(request, exc):  # noqa: ARG001
    return RedirectResponse(f"{БАЗА}/login?next={БАЗА}/admin", status_code=303)


@приложение.get(f"{БАЗА}/health", tags=["служебное"], response_model=HealthOut)
def здоровье() -> HealthOut:
    return HealthOut(status="ok", version=__version__, ai=settings.ai_включён)
