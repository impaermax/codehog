"""Общие зависимости запросов."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import получить_сессию
from app.models import User
from app.services.auth import COOKIE, Аутентификация


def текущий_пользователь(
    request: Request, сессия: Session = Depends(получить_сессию)
) -> User | None:
    """Пользователь из подписанной cookie. None — значит гость."""
    uid = Аутентификация.прочитать(request.cookies.get(COOKIE))
    if uid is None:
        return None
    return сессия.get(User, uid)


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
