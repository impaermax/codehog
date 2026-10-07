"""Sign-up, login and the current user from a signed cookie."""

from __future__ import annotations

import re

import bcrypt
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BonusGrant, Level, User

COOKIE = "codehog_session"
_signer = URLSafeSerializer(settings.secret_key, salt="codehog-auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class AuthError(Exception):
    """A human-readable reason why sign-up or login failed."""


class Auth:
    """Everything related to user accounts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    def register(self, email: str, username: str, password: str, level: Level) -> User:
        email = (email or "").strip().lower()
        username = (username or "").strip()

        if not EMAIL_RE.match(email):
            raise AuthError("Проверьте адрес почты")
        if len(username) < 2:
            raise AuthError("Имя — минимум два символа")
        if len(password) < 6:
            raise AuthError("Пароль — минимум шесть символов")
        if self.session.scalar(select(User).where(User.email == email)):
            raise AuthError("Такая почта уже зарегистрирована — войдите")
        if self.session.scalar(select(User).where(User.username == username)):
            username = f"{username}{self.session.query(User).count() + 1}"

        # Admin bonuses are a gift to those who were already registered when
        # they were granted. Without this mark a new user would receive every
        # past bonus on their first visit.
        last_bonus = self.session.scalar(select(func.max(BonusGrant.id))) or 0
        user = User(
            email=email,
            username=username,
            password_hash=self.hash_password(password),
            level=level,
            last_bonus_id=last_bonus,
        )
        self.session.add(user)
        self.session.commit()
        return user

    def login(self, identifier: str, password: str) -> User:
        """Accepts either the email or the username: the admin signs in as maks-admin."""
        value = (identifier or "").strip()
        user = self.session.scalar(select(User).where(User.email == value.lower()))
        if user is None:
            user = self.session.scalar(select(User).where(User.username == value))
        if not user or not self.verify_password(password, user.password_hash):
            raise AuthError("Неверный логин или пароль")
        return user

    @staticmethod
    def sign(user_id: int) -> str:
        """Session cookie value for the user."""
        return _signer.dumps({"uid": user_id})

    @staticmethod
    def read_session(cookie: str | None) -> int | None:
        """User id from a session cookie, or None if it is missing or forged."""
        if not cookie:
            return None
        try:
            data = _signer.loads(cookie)
        except BadSignature:
            return None
        return data.get("uid")
