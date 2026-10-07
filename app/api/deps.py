"""Shared request dependencies (Depends) and the single template engine."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import User
from app.services.auth import COOKIE, Auth
from app.services.text import markup

# Dependency aliases: FastAPI resolves them from the type annotation (Annotated style).
SessionDep = Annotated[Session, Depends(get_session)]

GUEST_COOKIE = "codehog_guest"
LANG_COOKIE = "lang"


def current_user(request: Request, session: SessionDep) -> User | None:
    """The user from the signed cookie. None means a guest."""
    user_id = Auth.read_session(request.cookies.get(COOKIE))
    if user_id is None:
        return None
    return session.get(User, user_id)


CurrentUser = Annotated[User | None, Depends(current_user)]


def require_user(user: CurrentUser) -> User:
    """Same as current_user, for JSON endpoints closed to guests: 401 without login.

    The login check lives in a dependency instead of being copied into every endpoint.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return user


def guest_token(request: Request) -> str:
    """Anonymous session id, used to link the test taken before sign-up."""
    return request.cookies.get(GUEST_COOKIE, "")


RequiredUser = Annotated[User, Depends(require_user)]
GuestToken = Annotated[str, Depends(guest_token)]


# The only template engine in the app.
#
# There used to be two, one in pages.py and one in admin.py, and settings added
# to one never reached the other. As a result the admin panel rendered links
# without the sub-path prefix and sent people to another site. Keeping a single
# instance makes that kind of drift impossible.
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["markup"] = markup
templates.env.globals["base_path"] = settings.base_path
templates.env.globals["contact_email"] = settings.contact_email


def template_context(request: Request, user: User | None, session: Session, **extra) -> dict:
    """Data every template needs: user, language, pending bonuses, active hedgehog.

    It lives here rather than in pages.py so the admin panel cannot miss some
    of the keys; that is exactly how the panel once failed with an UndefinedError.
    """
    from app.services.admin import AdminService
    from app.services.economy import Economy
    from app.services.i18n import LANGUAGES, get_translations, pick_language

    lang = pick_language(request.cookies.get(LANG_COOKIE))
    context = {
        "request": request,
        "user": user,
        "spins": 0,
        "equipped": {},
        "bonuses": [],
        "t": get_translations(lang),
        "lang": lang,
        "languages": LANGUAGES,
    }
    if user is not None:
        context["bonuses"] = [
            {"amount": grant.amount, "comment": grant.comment}
            for grant in AdminService(session).grant_pending(user)
        ]
        economy = Economy(session)
        economy.check_streak(user)
        context["spins"] = economy.available_spins(user)
        context["equipped"] = {
            owned.item.slot.value: owned.item.asset_key
            for owned in user.items
            if owned.is_equipped
        }
    context.update(extra)
    return context
