"""HTML pages rendered on the server."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    GUEST_COOKIE,
    LANG_COOKIE,
    CurrentUser,
    GuestToken,
    SessionDep,
    template_context,
    templates,
)
from app.config import settings
from app.models import Course, Item, Lesson, Level, TestAttempt, User
from app.services.auth import COOKIE, Auth, AuthError
from app.services.awards import MedalService
from app.services.course import CourseGenerator
from app.services.economy import SECTORS, Economy
from app.services.i18n import pick_language
from app.services.prefetch import prefetch_lessons
from app.services.testbank import AdaptiveTest

router = APIRouter()
BASE_PATH = settings.base_path
SESSION_MAX_AGE = 60 * 60 * 24 * 30


def _render(
    request: Request,
    template: str,
    user: User | None,
    session: Session,
    status_code: int = 200,
    **extra,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        template_context(request, user, session, **extra),
        status_code=status_code,
    )


def _signed_in(response: RedirectResponse, user: User) -> RedirectResponse:
    response.set_cookie(
        COOKIE, Auth.sign(user.id), max_age=SESSION_MAX_AGE, httponly=True, samesite="lax"
    )
    return response


def _active_course(session: Session, user: User) -> Course | None:
    return session.scalar(
        select(Course)
        .where(Course.user_id == user.id, Course.is_active.is_(True))
        .order_by(Course.id.desc())
    )


def _starter_skins(session: Session) -> list[Item]:
    """The nine tier-1 skins; the starter hedgehog is picked from them at sign-up."""
    return list(
        session.scalars(
            select(Item).where(Item.tier == 1, Item.is_active.is_(True)).order_by(Item.sort_order)
        )
    )


def _redirect_after_login(next_url: str) -> str:
    """Where to go after login: only inside the app, otherwise to the course.

    Only paths under our sub-path are accepted, so a link like
    ?next=https://other.site cannot lead someone away after they enter a password.
    """
    if next_url.startswith(f"{BASE_PATH}/") and not next_url.startswith("//"):
        return next_url
    return f"{BASE_PATH}/app"


# --- public pages ---


@router.get("/", response_class=HTMLResponse)
def landing(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    if user:
        return RedirectResponse(f"{BASE_PATH}/app", status_code=303)
    return _render(request, "landing.html", None, session)


@router.get("/test", response_class=HTMLResponse)
def test_page(request: Request, session: SessionDep):
    questions = [question.to_client() for question in AdaptiveTest.first_questions()]
    response = _render(request, "test.html", None, session, questions=questions)
    if not request.cookies.get(GUEST_COOKIE):
        response.set_cookie(GUEST_COOKIE, secrets.token_urlsafe(16), max_age=86400, httponly=True)
    return response


@router.get("/terms", response_class=HTMLResponse)
def terms(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """Terms of use. Open to everyone, guests included."""
    return _render(request, "terms.html", user, session)


@router.get("/privacy", response_class=HTMLResponse)
def privacy(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """Privacy policy. Open to everyone, guests included."""
    return _render(request, "privacy.html", user, session)


@router.get("/lang/{code}")
def set_language(code: str, request: Request):
    """Switch the interface language. Russian is the default."""
    back = request.headers.get("referer") or f"{BASE_PATH}/"
    response = RedirectResponse(back, status_code=303)
    response.set_cookie(
        LANG_COOKIE, pick_language(code), max_age=60 * 60 * 24 * 365, samesite="lax"
    )
    return response


# --- sign-up and login ---


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, session: SessionDep, guest: GuestToken):
    attempt = (
        session.scalar(
            select(TestAttempt)
            .where(TestAttempt.session_token == guest)
            .order_by(TestAttempt.id.desc())
        )
        if guest
        else None
    )
    level = attempt.determined_level if attempt else None
    return _render(
        request, "register.html", None, session, level=level, starter_skins=_starter_skins(session)
    )


@router.post("/register")
def register_submit(
    request: Request,
    session: SessionDep,
    guest: GuestToken,
    email: Annotated[str, Form()],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    level: Annotated[str, Form()] = "beginner",
    skin: Annotated[str, Form()] = "hog-1-1",
):
    try:
        chosen_level = Level(level)
    except ValueError:
        chosen_level = Level.BEGINNER
    try:
        user = Auth(session).register(email, username, password, chosen_level)
    except AuthError as e:
        # Everything entered goes back into the form; otherwise the chosen
        # hedgehog would silently reset to the first, blue one after an error.
        return _render(
            request,
            "register.html",
            None,
            session,
            status_code=400,
            error=str(e),
            level=chosen_level,
            starter_skins=_starter_skins(session),
            selected_skin=skin,
            entered={"email": email, "username": username},
        )

    weak_topics: list[str] = []
    experience = ""
    if guest:
        attempt = session.scalar(
            select(TestAttempt)
            .where(TestAttempt.session_token == guest)
            .order_by(TestAttempt.id.desc())
        )
        if attempt and attempt.user_id is None:
            attempt.user_id = user.id
            weak_topics = AdaptiveTest.weak_topics(attempt.answers)
            # Experience decides whether an intro module goes before the course.
            experience = attempt.experience
            session.commit()

    # The starter hedgehog chosen in the form is free. An unknown or foreign
    # sku is replaced with the first starter skin.
    starter = session.scalar(
        select(Item).where(Item.sku == skin, Item.tier == 1, Item.is_active.is_(True))
    )
    starter = starter or next(iter(_starter_skins(session)), None)
    if starter is not None:
        Economy(session).buy(user, starter)

    CourseGenerator(session).create(user, weak_topics, experience=experience)
    prefetch_lessons(user.id)  # the next lessons are prepared while the first one is read
    return _signed_in(RedirectResponse(f"{BASE_PATH}/app", status_code=303), user)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: SessionDep, next: str = ""):
    return _render(request, "login.html", None, session, next=_redirect_after_login(next))


@router.post("/login")
def login_submit(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "",
):
    try:
        user = Auth(session).login(email, password)
    except AuthError as e:
        return _render(
            request,
            "login.html",
            None,
            session,
            status_code=400,
            error=str(e),
            next=_redirect_after_login(next),
        )
    return _signed_in(RedirectResponse(_redirect_after_login(next), status_code=303), user)


@router.get("/logout")
def logout():
    response = RedirectResponse(f"{BASE_PATH}/", status_code=303)
    response.delete_cookie(COOKIE)
    return response


# --- learner pages ---


@router.get("/app", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    if not user:
        return RedirectResponse(f"{BASE_PATH}/", status_code=303)
    course = _active_course(session, user) or CourseGenerator(session).create(user)
    return _render(request, "app.html", user, session, course=course, sectors=SECTORS)


@router.get("/lesson/{lesson_id}", response_class=HTMLResponse)
def lesson_page(
    lesson_id: int,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    if not user:
        return RedirectResponse(f"{BASE_PATH}/", status_code=303)
    lesson = session.get(Lesson, lesson_id)
    if lesson is None or lesson.module.course.user_id != user.id:
        return RedirectResponse(f"{BASE_PATH}/app", status_code=303)

    # Requirement 2.5: no moving on until the previous lesson is completed.
    # The check is done on the server, so a direct link cannot bypass it.
    if lesson.id not in lesson.module.course.open_lessons:
        return RedirectResponse(f"{BASE_PATH}/app?locked=1", status_code=303)

    attempt = session.scalar(
        select(TestAttempt).where(TestAttempt.user_id == user.id).order_by(TestAttempt.id.desc())
    )
    weak_topics = AdaptiveTest.weak_topics(attempt.answers) if attempt else []
    CourseGenerator(session).fill_lesson(lesson, user, weak_topics)
    prefetch_lessons(user.id)  # top up the buffer of upcoming lessons
    return _render(request, "lesson.html", user, session, lesson=lesson)


@router.get("/profile", response_class=HTMLResponse)
def profile(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """Profile: progress, coins, streak, hedgehog collection and medals (requirement 3.6, UC-7)."""
    if not user:
        return RedirectResponse(f"{BASE_PATH}/", status_code=303)
    medals = MedalService(session)
    # Catch up on what was earned outside lessons: purchases, the wheel, the
    # placement test. Otherwise the medal would wait for the next completed lesson.
    medals.check(user)
    collection = sorted(
        (owned for owned in user.items if owned.item.tier), key=lambda owned: owned.item.sort_order
    )
    return _render(
        request,
        "profile.html",
        user,
        session,
        course=_active_course(session, user),
        collection=collection,
        medals=medals.all_with_status(user),
    )


@router.get("/shop", response_class=HTMLResponse)
def shop(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    """Skin shop: six tiers of nine hedgehogs, tiers unlock as modules are completed."""
    if not user:
        return RedirectResponse(f"{BASE_PATH}/", status_code=303)
    economy = Economy(session)
    skins = session.scalars(
        select(Item).where(Item.is_active.is_(True), Item.tier >= 1).order_by(Item.sort_order)
    ).all()
    tiers: dict[int, list[Item]] = {}
    for skin in skins:
        tiers.setdefault(skin.tier, []).append(skin)
    return _render(
        request,
        "shop.html",
        user,
        session,
        tiers=sorted(tiers.items()),
        owned={owned.item_id: owned for owned in user.items},
        unlocked_tier=economy.unlocked_tier(user),
        free_starter=not economy.has_skin(user),
    )
