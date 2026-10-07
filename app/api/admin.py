"""Admin panel: analytics, bonuses, progress reset and shortcuts."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, template_context, templates
from app.config import settings
from app.models import Course, Item, User
from app.services.admin import AdminService
from app.services.economy import Economy

router = APIRouter(prefix="/admin")
BASE_PATH = settings.base_path


class LoginRequiredError(Exception):
    """Someone without admin rights opened the panel: send them to the login page."""


def admin_only(user: CurrentUser) -> User:
    """Guests and regular learners are sent to login with a note that the panel is for admins.

    Learners used to get a 404 and could not tell the page existed.
    They still cannot see any panel data: signing in as the admin is required.
    """
    if user is None or not user.is_admin:
        raise LoginRequiredError
    return user


AdminUser = Annotated[User, Depends(admin_only)]


@router.get("", response_class=HTMLResponse)
def admin_panel(request: Request, admin: AdminUser, session: SessionDep):
    stats = AdminService(session).collect()
    return templates.TemplateResponse(
        request, "admin.html", template_context(request, admin, session, stats=stats)
    )


@router.post("/bonus")
def grant_bonus(
    admin: AdminUser,
    session: SessionDep,
    amount: Annotated[int, Form()],
    comment: Annotated[str, Form()] = "",
):
    amount = max(1, min(100_000, amount))
    AdminService(session).grant_to_all(amount, comment or "подарок от команды", admin.username)
    return RedirectResponse(f"{BASE_PATH}/admin", status_code=303)


@router.post("/reset")
def reset_self(admin: AdminUser, session: SessionDep):
    """Wipe the admin's own progress to walk through the funnel again."""
    AdminService(session).reset(admin)
    return RedirectResponse(f"{BASE_PATH}/app", status_code=303)


@router.post("/reset/{user_id}")
def reset_user(user_id: int, admin: AdminUser, session: SessionDep):
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    AdminService(session).reset(target)
    return RedirectResponse(f"{BASE_PATH}/admin", status_code=303)


@router.post("/unlock")
def unlock_all(admin: AdminUser, session: SessionDep):
    """Give the admin all 54 skins, to check them without buying one by one.

    Buying makes a skin active, so the active hedgehog is remembered first and
    restored at the end; otherwise the last skin of the catalog would stay active.
    """
    economy = Economy(session)
    previously_active = next((owned for owned in admin.items if owned.is_equipped), None)
    for item in session.scalars(select(Item).where(Item.is_active.is_(True))).all():
        economy.buy(admin, item)
    if previously_active is not None:
        economy.equip(admin, previously_active)
        session.commit()
    return RedirectResponse(f"{BASE_PATH}/shop", status_code=303)


@router.post("/complete")
def complete_course(admin: AdminUser, session: SessionDep):
    """Mark every lesson as completed: a quick way to see the end of the funnel."""
    course = session.scalar(
        select(Course).where(Course.user_id == admin.id).order_by(Course.id.desc())
    )
    if course is None:
        raise HTTPException(status_code=400, detail="Курса нет")
    economy = Economy(session)
    for lesson in course.all_lessons:
        if not lesson.is_completed:
            lesson.is_completed = True
            for task in lesson.tasks:
                task.is_completed = True
            economy.complete_lesson(admin, lesson.xp_reward)
    session.commit()
    return RedirectResponse(f"{BASE_PATH}/app", status_code=303)
