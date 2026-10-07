"""Панель администратора: аналитика, бонусы, сброс, быстрые действия."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import контекст_шаблона, текущий_пользователь, шаблоны
from app.config import settings
from app.database import получить_сессию
from app.models import Course, Item, Lesson, User
from app.services.admin import Админка
from app.services.economy import Экономика

роутер = APIRouter(prefix="/admin")


class НужнаАвторизация(Exception):
    """Гость постучался в панель — отправляем на страницу входа."""


def только_админ(юзер: User | None = Depends(текущий_пользователь)) -> User:
    """Гостя ведём на вход, вошедшего не-админа не существует для панели (404)."""
    if юзер is None:
        raise НужнаАвторизация
    if not юзер.is_admin:
        raise HTTPException(status_code=404, detail="Не найдено")
    return юзер


@роутер.get("", response_class=HTMLResponse)
def панель(request: Request, админ: User = Depends(только_админ),
           сессия: Session = Depends(получить_сессию)):
    аналитика = Админка(сессия).собрать()
    return шаблоны.TemplateResponse(
        request, "admin.html", контекст_шаблона(request, админ, сессия, а=аналитика)
    )


@роутер.post("/bonus")
def раздать_бонус(amount: int = Form(...), comment: str = Form(""),
                  админ: User = Depends(только_админ),
                  сессия: Session = Depends(получить_сессию)):
    сумма = max(1, min(100_000, amount))
    Админка(сессия).начислить_всем(сумма, comment or "подарок от команды", админ.username)
    return RedirectResponse(f"{settings.base_path}/admin", status_code=303)


@роутер.post("/reset")
def сбросить_себя(админ: User = Depends(только_админ),
                  сессия: Session = Depends(получить_сессию)):
    """Обнуляет прогресс самого админа — для повторной проверки воронки."""
    Админка(сессия).сбросить(админ)
    return RedirectResponse(f"{settings.base_path}/app", status_code=303)


@роутер.post("/reset/{user_id}")
def сбросить_пользователя(user_id: int, админ: User = Depends(только_админ),
                          сессия: Session = Depends(получить_сессию)):
    цель = сессия.get(User, user_id)
    if цель is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    Админка(сессия).сбросить(цель)
    return RedirectResponse(f"{settings.base_path}/admin", status_code=303)


@роутер.post("/unlock")
def открыть_всё(админ: User = Depends(только_админ),
                сессия: Session = Depends(получить_сессию)):
    """Выдаёт админу все 54 скина — чтобы проверить их, не покупая по одному.

    Покупка сама делает скин активным, поэтому активный ёж запоминается
    заранее и возвращается в конце: иначе им остался бы последний в каталоге.
    """
    экономика = Экономика(сессия)
    был = next((п for п in админ.items if п.is_equipped), None)
    for предмет in сессия.scalars(select(Item).where(Item.is_active.is_(True))).all():
        экономика.купить(админ, предмет)
    if был is not None:
        экономика.надеть(админ, был)
        сессия.commit()
    return RedirectResponse(f"{settings.base_path}/shop", status_code=303)


@роутер.post("/complete")
def пройти_курс(админ: User = Depends(только_админ),
                сессия: Session = Depends(получить_сессию)):
    """Отмечает все уроки пройденными — быстрый способ увидеть конец воронки."""
    курс = сессия.scalar(
        select(Course).where(Course.user_id == админ.id).order_by(Course.id.desc())
    )
    if курс is None:
        raise HTTPException(status_code=400, detail="Курса нет")
    экономика = Экономика(сессия)
    for урок in курс.все_уроки:
        if not урок.is_completed:
            урок.is_completed = True
            for з in урок.tasks:
                з.is_completed = True
            экономика.отметить_урок(админ, урок.xp_reward)
    сессия.commit()
    return RedirectResponse(f"{settings.base_path}/app", status_code=303)
