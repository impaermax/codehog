"""Настройки приложения. Читаются из .env, но у всего есть разумный дефолт."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent


def _читать_env(путь: Path) -> None:
    """Простой разбор .env без внешних зависимостей."""
    if not путь.exists():
        return
    for строка in путь.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if not строка or строка.startswith("#") or "=" not in строка:
            continue
        ключ, _, значение = строка.partition("=")
        os.environ.setdefault(ключ.strip(), значение.strip())


_читать_env(КОРЕНЬ / ".env")


@dataclass(frozen=True)
class Settings:
    """Конфигурация приложения одним объектом."""

    api_key: str = field(default_factory=lambda: os.getenv("EXPLABS_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("EXPLABS_BASE_URL", "https://api.experientiallabs.ai/v1")
    )
    course_model: str = field(default_factory=lambda: os.getenv("COURSE_MODEL", "deepseek-v4-flash"))
    fallback_model: str = field(
        default_factory=lambda: os.getenv("COURSE_MODEL_FALLBACK", "gpt-5.4-mini")
    )
    admin_password: str = field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD", "codehog-admin")
    )
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me"))
    # Почта для обращений по личным данным. Пусто — строка на странице политики не выводится
    contact_email: str = field(default_factory=lambda: os.getenv("CONTACT_EMAIL", ""))
    # Подкаталог, в котором живёт приложение: "" для корня домена,
    # "/codehog" — чтобы открывалось по https://maks.my/codehog
    base_path: str = field(
        default_factory=lambda: "/" + os.getenv("BASE_PATH", "").strip("/") if os.getenv("BASE_PATH", "").strip("/") else ""
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{КОРЕНЬ / 'data' / 'codehog.db'}")
    )
    # Ограничения песочницы для проверки кода ученика
    code_timeout_sec: float = 5.0
    code_memory_mb: int = 128
    code_output_limit: int = 10_000

    @property
    def ai_включён(self) -> bool:
        """Без ключа приложение работает целиком, просто курс берётся шаблонный."""
        return bool(self.api_key)


settings = Settings()
