"""Страницы приложения."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import контекст_шаблона, текущий_пользователь, токен_гостя, шаблоны
from app.config import settings
from app.database import получить_сессию
from app.models import Course, Item, Lesson, TestAttempt, User, UserItem, Уровень
from app.services.auth import COOKIE, Аутентификация, ОшибкаВхода
from app.services.awards import Медали
from app.services.admin import Админка
from app.services.course import ГенераторКурса
from app.services.prefetch import запустить as подготовить_фоном
from app.services.economy import СЕКТОРА, Экономика
from app.services.i18n import ЯЗЫКИ, выбрать, перевод
from app.services.testbank import АдаптивныйТест

роутер = APIRouter()
БАЗА = settings.base_path


def _контекст(request: Request, юзер: User | None, сессия: Session, **прочее) -> dict:
    """Тонкая обёртка: вся логика в deps.контекст_шаблона."""
    return контекст_шаблона(request, юзер, сессия, **прочее)


@роутер.get("/", response_class=HTMLResponse)
def лендинг(request: Request, юзер: User | None = Depends(текущий_пользователь),
            сессия: Session = Depends(получить_сессию)):
    if юзер:
        return RedirectResponse(f"{БАЗА}/app", status_code=303)
    return шаблоны.TemplateResponse(
        request, "landing.html", _контекст(request, None, сессия))


@роутер.get("/test", response_class=HTMLResponse)
def страница_теста(request: Request, сессия: Session = Depends(получить_сессию)):
    вопросы = [в.для_клиента() for в in АдаптивныйТест.первые_вопросы()]
    ответ = шаблоны.TemplateResponse(
        request, "test.html", _контекст(request, None, сессия, вопросы=вопросы)
    )
    if not request.cookies.get("codehog_guest"):
        ответ.set_cookie("codehog_guest", secrets.token_urlsafe(16), max_age=86400, httponly=True)
    return ответ


@роутер.get("/register", response_class=HTMLResponse)
def страница_регистрации(request: Request, сессия: Session = Depends(получить_сессию),
                         гость: str = Depends(токен_гостя)):
    попытка = сессия.scalar(
        select(TestAttempt).where(TestAttempt.session_token == гость)
        .order_by(TestAttempt.id.desc())
    ) if гость else None
    уровень = попытка.determined_level if попытка else None
    return шаблоны.TemplateResponse(
        request, "register.html",
        _контекст(request, None, сессия, уровень=уровень, попытка=попытка),
    )


@роутер.post("/register")
def регистрация(
    request: Request,
    email: str = Form(...), username: str = Form(...), password: str = Form(...),
    level: str = Form("beginner"),
    сессия: Session = Depends(получить_сессию), гость: str = Depends(токен_гостя),
):
    авторизация = Аутентификация(сессия)
    try:
        уровень = Уровень(level)
    except ValueError:
        уровень = Уровень.НОВИЧОК
    try:
        юзер = авторизация.зарегистрировать(email, username, password, уровень)
    except ОшибкаВхода as e:
        return шаблоны.TemplateResponse(
        request, "register.html",
            _контекст(request, None, сессия, ошибка=str(e), уровень=уровень, попытка=None),
            status_code=400,
        )

    слабые: list[str] = []
    if гость:
        попытка = сессия.scalar(
            select(TestAttempt).where(TestAttempt.session_token == гость)
            .order_by(TestAttempt.id.desc())
        )
        if попытка and попытка.user_id is None:
            попытка.user_id = юзер.id
            слабые = АдаптивныйТест.слабые_темы(попытка.ответы)
            сессия.commit()

    ГенераторКурса(сессия).создать(юзер, слабые)
    подготовить_фоном(юзер.id)          # следующие уроки готовятся, пока человек читает первый
    ответ = RedirectResponse(f"{БАЗА}/app", status_code=303)
    ответ.set_cookie(COOKIE, Аутентификация.подписать(юзер.id), max_age=60 * 60 * 24 * 30,
                     httponly=True, samesite="lax")
    return ответ


@роутер.get("/login", response_class=HTMLResponse)
def страница_входа(request: Request, сессия: Session = Depends(получить_сессию)):
    return шаблоны.TemplateResponse(
        request, "login.html", _контекст(request, None, сессия))


@роутер.post("/login")
def вход(request: Request, email: str = Form(...), password: str = Form(...),
         сессия: Session = Depends(получить_сессию)):
    try:
        юзер = Аутентификация(сессия).войти(email, password)
    except ОшибкаВхода as e:
        return шаблоны.TemplateResponse(
        request, "login.html", _контекст(request, None, сессия, ошибка=str(e)), status_code=400
        )
    ответ = RedirectResponse(f"{БАЗА}/app", status_code=303)
    ответ.set_cookie(COOKIE, Аутентификация.подписать(юзер.id), max_age=60 * 60 * 24 * 30,
                     httponly=True, samesite="lax")
    return ответ


@роутер.get("/lang/{code}")
def сменить_язык(code: str, request: Request):
    """Переключение языка. Русский по умолчанию, чеченский — для своих."""
    назад = request.headers.get("referer") or f"{БАЗА}/"
    ответ = RedirectResponse(назад, status_code=303)
    ответ.set_cookie("lang", выбрать(code), max_age=60 * 60 * 24 * 365, samesite="lax")
    return ответ


@роутер.get("/logout")
def выход():
    ответ = RedirectResponse(f"{БАЗА}/", status_code=303)
    ответ.delete_cookie(COOKIE)
    return ответ


@роутер.get("/app", response_class=HTMLResponse)
def кабинет(request: Request, юзер: User | None = Depends(текущий_пользователь),
            сессия: Session = Depends(получить_сессию)):
    if not юзер:
        return RedirectResponse(f"{БАЗА}/", status_code=303)
    курс = сессия.scalar(
        select(Course).where(Course.user_id == юзер.id, Course.is_active.is_(True))
        .order_by(Course.id.desc())
    )
    if курс is None:
        курс = ГенераторКурса(сессия).создать(юзер)
    return шаблоны.TemplateResponse(
        request, "app.html", _контекст(request, юзер, сессия, курс=курс, сектора=СЕКТОРА)
    )


@роутер.get("/lesson/{lesson_id}", response_class=HTMLResponse)
def урок(lesson_id: int, request: Request,
         юзер: User | None = Depends(текущий_пользователь),
         сессия: Session = Depends(получить_сессию)):
    if not юзер:
        return RedirectResponse(f"{БАЗА}/", status_code=303)
    урок_ = сессия.get(Lesson, lesson_id)
    if урок_ is None or урок_.module.course.user_id != юзер.id:
        return RedirectResponse(f"{БАЗА}/app", status_code=303)

    # Требование 2.5: пока предыдущий урок не пройден, дальше нельзя.
    # Проверка именно на сервере — прямая ссылка её не обходит.
    if урок_.id not in урок_.module.course.открытые_уроки:
        return RedirectResponse(f"{БАЗА}/app?закрыт=1", status_code=303)

    слабые: list[str] = []
    попытка = сессия.scalar(
        select(TestAttempt).where(TestAttempt.user_id == юзер.id).order_by(TestAttempt.id.desc())
    )
    if попытка:
        слабые = АдаптивныйТест.слабые_темы(попытка.ответы)
    ГенераторКурса(сессия).наполнить_урок(урок_, юзер, слабые)
    подготовить_фоном(юзер.id)          # пополняем буфер следующих уроков
    return шаблоны.TemplateResponse(
        request, "lesson.html", _контекст(request, юзер, сессия, урок=урок_))


@роутер.get("/profile", response_class=HTMLResponse)
def профиль(request: Request, юзер: User | None = Depends(текущий_пользователь),
            сессия: Session = Depends(получить_сессию)):
    """Профиль: прогресс, монеты, серия и полученные медали (требование 3.6, UC-7)."""
    if not юзер:
        return RedirectResponse(f"{БАЗА}/", status_code=303)
    медали = Медали(сессия)
    # Догоняем то, что заработано вне урока: покупки, колесо, вводный тест.
    # Иначе условие выполнено, а медали нет до следующего пройденного урока.
    медали.проверить(юзер)
    курс = сессия.scalar(
        select(Course).where(Course.user_id == юзер.id, Course.is_active.is_(True))
        .order_by(Course.id.desc())
    )
    return шаблоны.TemplateResponse(request, "profile.html", _контекст(
        request, юзер, сессия,
        курс=курс,
        медали=медали.все_с_отметкой(юзер),
        показатели=медали.показатели(юзер),
    ))


@роутер.get("/shop", response_class=HTMLResponse)
def магазин(request: Request, юзер: User | None = Depends(текущий_пользователь),
            сессия: Session = Depends(получить_сессию)):
    if not юзер:
        return RedirectResponse(f"{БАЗА}/", status_code=303)
    предметы = сессия.scalars(
        select(Item).where(Item.is_active.is_(True)).order_by(Item.sort_order)
    ).all()
    мои = {п.item_id: п for п in юзер.items}
    return шаблоны.TemplateResponse(
        request, "shop.html", _контекст(request, юзер, сессия, предметы=предметы, мои=мои)
    )
