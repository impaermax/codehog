"""Application settings. Read from .env, with a sensible default for everything."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_env(path: Path) -> None:
    """Minimal .env parser, so no extra dependency is needed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_read_env(ROOT / ".env")


def _base_path() -> str:
    """Sub-path the app is served from: "" for the domain root, "/codehog" for maks.my/codehog."""
    raw = os.getenv("BASE_PATH", "").strip("/")
    return f"/{raw}" if raw else ""


@dataclass(frozen=True)
class Settings:
    """All configuration in one object."""

    api_key: str = field(default_factory=lambda: os.getenv("EXPLABS_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv("EXPLABS_BASE_URL", "https://api.experientiallabs.ai/v1")
    )
    course_model: str = field(
        default_factory=lambda: os.getenv("COURSE_MODEL", "deepseek-v4-flash")
    )
    fallback_model: str = field(
        default_factory=lambda: os.getenv("COURSE_MODEL_FALLBACK", "gpt-5.4-mini")
    )
    admin_password: str = field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD", "codehog-admin")
    )
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me")
    )
    # Contact address for personal data requests. Empty hides the line on the privacy page.
    contact_email: str = field(default_factory=lambda: os.getenv("CONTACT_EMAIL", ""))
    base_path: str = field(default_factory=_base_path)
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'codehog.db'}"
        )
    )
    # Sandbox limits for running learner code
    code_timeout_sec: float = 5.0
    code_memory_mb: int = 128
    code_output_limit: int = 10_000

    @property
    def ai_enabled(self) -> bool:
        """Without a key the app still works in full, lessons just come from templates."""
        return bool(self.api_key)


settings = Settings()
