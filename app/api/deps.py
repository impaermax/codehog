"""Общие зависимости запросов (Depends) и единый шаблонизатор."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import получить_сессию
from app.models import User
from app.services.auth import COOKIE, Аутентификация
from app.services.text import разметка


def текущий_пользователь(
    request: Request, сессия: Session = Depends(получить_сессию)
) -> User | None:
    """Пользователь из подписанной cookie. None — значит гость."""
    uid = Аутентификация.прочитать(request.cookies.get(COOKIE))
    if uid is None:
        return None
    return сессия.get(User, uid)


def нужен_пользователь(юзер: User | None = Depends(текущий_пользователь)) -> User:
    """То же, но для JSON-ручек, куда гостю нельзя: без входа — 401.

    Проверка входа живёт в зависимости, а не копируется в каждую ручку.
    """
    if юзер is None:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return юзер

# Единственный экземпляр шаблонизатора на всё приложение.
#
# Раньше их было два — свой в pages.py и свой в admin.py, — и настройки,
# добавленные в один, не доезжали до другого. Из-за этого админка рисовала
# ссылки без префикса подкаталога и уводила на чужой сайт. Держим один,
# чтобы такая рассинхронизация была невозможна в принципе.
шаблоны = Jinja2Templates(directory="app/templates")
шаблоны.env.filters["разметка"] = разметка
шаблоны.env.globals["база"] = settings.base_path
шаблоны.env.globals["почта_для_обращений"] = settings.contact_email


def контекст_шаблона(request: Request, юзер, сессия, **прочее) -> dict:
    """Данные, нужные каждому шаблону: пользователь, язык, бонусы, экипировка.

    Живёт здесь, а не в pages.py, чтобы админка не забывала часть ключей —
    именно на этом панель однажды упала с UndefinedError.
    """
    from app.services.admin import Админка
    from app.services.economy import Экономика
    from app.services.i18n import ЯЗЫКИ, выбрать, перевод

    язык = выбрать(request.cookies.get("lang"))
    основа = {
        "request": request, "user": юзер, "вращений": 0, "надето": {}, "бонусы": [],
        "т": перевод(язык), "язык": язык, "языки": ЯЗЫКИ,
    }
    if юзер is not None:
        основа["бонусы"] = [
            {"amount": б.amount, "comment": б.comment}
            for б in Админка(сессия).выдать_ожидающие(юзер)
        ]
        экономика = Экономика(сессия)
        экономика.проверить_стрик(юзер)
        основа["вращений"] = экономика.доступно_вращений(юзер)
        основа["надето"] = {
            п.item.slot.value: п.item.asset_key for п in юзер.items if п.is_equipped
        }
    основа.update(прочее)
    return основа


def токен_гостя(request: Request) -> str:
    """Идентификатор анонимной сессии — чтобы связать тест до регистрации."""
    return request.cookies.get("codehog_guest", "")
