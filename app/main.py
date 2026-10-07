"""Entry point: builds the app, prepares the database and serves static files."""

from __future__ import annotations

import fcntl
import logging
import re
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import actions, admin, pages
from app.api.admin import LoginRequiredError
from app.api.schemas import HealthOut
from app.config import settings
from app.database import SessionLocal, create_tables, engine
from app.services.admin import AdminService
from app.services.auth import COOKIE, Auth
from app.services.awards import seed_rewards
from app.services.course import reset_template_lessons
from app.services.migrate import upgrade_schema
from app.services.seed import seed_catalog

# Server log: time, level (INFO, WARNING, ERROR, CRITICAL), source and message.
# Under systemd everything goes to the system journal: journalctl -u codehog
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("codehog")

BASE_PATH = settings.base_path  # "" or "/codehog"

ERROR_PAGE = (
    "<!doctype html><meta charset=utf-8><title>Ошибка</title>"
    "<body style='font-family:sans-serif;background:#101619;color:#F2F5EF;"
    "display:grid;place-items:center;height:100vh;margin:0'>"
    "<div style='text-align:center'><h1>Что-то пошло не так</h1>"
    "<p>Ошибка записана, мы её разберём. Обновите страницу.</p></div>"
)


def init_database() -> None:
    """Create and upgrade the schema, then seed the reference data.

    There are several workers, and without a lock they would create tables at
    the same time and one would fail with "table already exists". So exactly
    one process initialises the database while the others wait.
    """
    lock_path = Path(tempfile.gettempdir()) / "codehog-init.lock"
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            create_tables()
            upgrade_schema(engine)
            session = SessionLocal()
            try:
                skins_added = seed_catalog(session)
                medals_added, memes_added = seed_rewards(session)
                if cleared := reset_template_lessons(session):
                    logger.info("lessons with the old template cleared: %s", cleared)
                admin_user = AdminService(session).create_admin(settings.admin_password)
            finally:
                session.close()
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    logger.info("admin login: %s, password from ADMIN_PASSWORD", admin_user.username)
    logger.info("added: %s skins, %s medals, %s memes", skins_added, medals_added, memes_added)
    logger.info("CodeHogwarts %s is ready", __version__)
    logger.info(
        "course model: %s (API key %s)",
        settings.course_model,
        "set" if settings.ai_enabled else "not set, using ready and fallback lessons",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """What to do on server start and stop (lifespan replaces the deprecated on_event)."""
    init_database()
    yield


def _operation_id(route: APIRoute) -> str:
    """Short OpenAPI operationId from the method and path, e.g. post_hog_shop_buy_sku."""
    path = route.path_format.removeprefix(BASE_PATH)
    method = sorted(route.methods)[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", f"{method}_{path}").strip("_")


app = FastAPI(
    title="CodeHogwarts",
    version=__version__,
    description="Python trainer. The JSON API used by the site's pages lives under /hog.",
    lifespan=lifespan,
    # The docs and the schema also live under the sub-path; otherwise Swagger
    # on maks.my would request /openapi.json from a neighbouring site.
    docs_url=f"{BASE_PATH}/hog/docs",
    redoc_url=None,
    openapi_url=f"{BASE_PATH}/hog/openapi.json",
    generate_unique_id_function=_operation_id,
)
app.mount(f"{BASE_PATH}/static", StaticFiles(directory="app/static"), name="static")
# Every route lives under BASE_PATH: with BASE_PATH=codehog the whole app
# is served at https://maks.my/codehog
app.include_router(pages.router, prefix=BASE_PATH, tags=["pages"])
app.include_router(actions.router, prefix=BASE_PATH)
app.include_router(admin.router, prefix=BASE_PATH, tags=["admin"])


@app.middleware("http")
async def log_errors(request: Request, call_next):
    """Log every unhandled failure and give the user a clear response.

    The log gets the request method and path, the user id (or "guest") and the
    full traceback, so the failure can be found and reproduced. The traceback
    never leaves the server: JSON requests get {"detail": "..."} with status 500,
    pages get a short message.
    """
    try:
        return await call_next(request)
    except Exception:
        user_id = Auth.read_session(request.cookies.get(COOKIE))
        logger.exception(
            "failure %s %s, user %s", request.method, request.url.path, user_id or "guest"
        )
        if "/hog/" in request.url.path:
            return JSONResponse(
                {"detail": "Сервер не справился с запросом. Попробуйте ещё раз."},
                status_code=500,
            )
        return HTMLResponse(ERROR_PAGE, status_code=500)


@app.exception_handler(RequestValidationError)
def _invalid_request(request: Request, exc: RequestValidationError):
    """The body did not match the schema: details go to the log, the user gets one line.

    FastAPI's default response is a list of per-field errors. The frontend shows
    detail as text, so it is returned as a string and the details stay in the log.
    """
    logger.warning("invalid request %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        {"detail": "Сервер не понял запрос. Обновите страницу и попробуйте снова."},
        status_code=422,
    )


@app.exception_handler(LoginRequiredError)
def _redirect_to_login(request: Request, exc: LoginRequiredError):
    return RedirectResponse(f"{BASE_PATH}/login?next={BASE_PATH}/admin", status_code=303)


@app.get(f"{BASE_PATH}/health", tags=["service"], response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__, ai=settings.ai_enabled)
