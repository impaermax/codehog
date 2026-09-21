"""Регистрация, вход и текущий пользователь из подписанной cookie."""
from __future__ import annotations

import re

import bcrypt
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, Уровень

COOKIE = "codehog_session"
_подписчик = URLSafeSerializer(settings.secret_key, salt="codehog-auth")

ПОЧТА = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class ОшибкаВхода(Exception):
    """Понятная человеку причина, почему не пустило."""


class Аутентификация:
    """Всё, что связано с учётной записью."""

    def __init__(self, сессия: Session) -> None:
        self.сессия = сессия

    @staticmethod
    def хеш(пароль: str) -> str:
        return bcrypt.hashpw(пароль.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def сверить(пароль: str, хеш: str) -> bool:
        try:
            return bcrypt.checkpw(пароль.encode("utf-8"), хеш.encode("utf-8"))
        except ValueError:
            return False

    def зарегистрировать(self, email: str, username: str, пароль: str, уровень: Уровень) -> User:
        email = (email or "").strip().lower()
        username = (username or "").strip()

        if not ПОЧТА.match(email):
            raise ОшибкаВхода("Проверьте адрес почты")
        if len(username) < 2:
            raise ОшибкаВхода("Имя — минимум два символа")
        if len(пароль) < 6:
            raise ОшибкаВхода("Пароль — минимум шесть символов")
        if self.сессия.scalar(select(User).where(User.email == email)):
            raise ОшибкаВхода("Такая почта уже зарегистрирована — войдите")
        if self.сессия.scalar(select(User).where(User.username == username)):
            username = f"{username}{self.сессия.query(User).count() + 1}"

        юзер = User(
            email=email, username=username,
            password_hash=self.хеш(пароль), level=уровень,
        )
        self.сессия.add(юзер)
        self.сессия.commit()
        return юзер

    def войти(self, логин: str, пароль: str) -> User:
        """Пускаем и по почте, и по имени пользователя: админ входит как maks-admin."""
        значение = (логин or "").strip()
        юзер = self.сессия.scalar(select(User).where(User.email == значение.lower()))
        if юзер is None:
            юзер = self.сессия.scalar(select(User).where(User.username == значение))
        if not юзер or not self.сверить(пароль, юзер.password_hash):
            raise ОшибкаВхода("Неверный логин или пароль")
        return юзер

    def найти(self, user_id: int) -> User | None:
        return self.сессия.get(User, user_id)

    @staticmethod
    def подписать(user_id: int) -> str:
        return _подписчик.dumps({"uid": user_id})

    @staticmethod
    def прочитать(значение: str | None) -> int | None:
        if not значение:
            return None
        try:
            данные = _подписчик.loads(значение)
        except BadSignature:
            return None
        return данные.get("uid")
