"""Клиент к шлюзу ExperientialLabs. OpenAI-совместимый, поэтому запрос простой.

Ключевое: приложение обязано работать и без ключа. Если ключа нет или модель
недоступна, вызывающий код берёт шаблонный курс — человек этого не замечает.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

лог = logging.getLogger("codehog.ai")


class ИИНедоступен(Exception):
    """Модель не ответила или ответила мусором."""


@dataclass
class Ответ:
    текст: str
    модель: str
    стоимость: float = 0.0
    токенов: int = 0


class КлиентИИ:
    """Тонкая обёртка над /chat/completions с запасной моделью."""

    def __init__(self, таймаут: float = 90.0) -> None:
        self.таймаут = таймаут

    @property
    def доступен(self) -> bool:
        return settings.ai_включён

    def спросить(
        self,
        системный: str,
        запрос: str,
        модель: str | None = None,
        максимум_токенов: int = 3000,
        температура: float = 0.4,
    ) -> Ответ:
        if not self.доступен:
            raise ИИНедоступен("Ключ EXPLABS_API_KEY не задан")

        модели = [модель or settings.course_model, settings.fallback_model]
        последняя_ошибка = "неизвестно"
        for имя in модели:
            try:
                return self._вызов(имя, системный, запрос, максимум_токенов, температура)
            except Exception as e:
                последняя_ошибка = str(e)[:200]
                лог.warning("модель %s не ответила: %s", имя, последняя_ошибка)
        raise ИИНедоступен(последняя_ошибка)

    def _вызов(
        self, модель: str, системный: str, запрос: str, максимум: int, температура: float
    ) -> Ответ:
        тело = {
            "model": модель,
            "messages": [
                {"role": "system", "content": системный},
                {"role": "user", "content": запрос},
            ],
            "max_tokens": максимум,
            "temperature": температура,
        }
        with httpx.Client(timeout=self.таймаут) as клиент:
            ответ = клиент.post(
                f"{settings.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.api_key}"},
                json=тело,
            )
        if ответ.status_code != 200:
            raise ИИНедоступен(f"HTTP {ответ.status_code}: {ответ.text[:200]}")
        данные = ответ.json()
        if "error" in данные:
            raise ИИНедоступен(данные["error"].get("message", "ошибка шлюза"))
        выбор = данные["choices"][0]
        текст = выбор["message"].get("content") or ""
        if not текст.strip():
            raise ИИНедоступен("пустой ответ модели")
        использование = данные.get("usage", {}) or {}
        return Ответ(
            текст=текст,
            модель=модель,
            стоимость=float(использование.get("cost", 0) or 0),
            токенов=int(использование.get("total_tokens", 0) or 0),
        )

    @staticmethod
    def достать_json(текст: str) -> dict:
        """Модели любят обрамлять JSON пояснениями и ```-блоками. Вытаскиваем объект."""
        текст = текст.strip()
        блок = re.search(r"```(?:json)?\s*(.+?)```", текст, re.S)
        if блок:
            текст = блок.group(1).strip()
        начало = текст.find("{")
        конец = текст.rfind("}")
        if начало == -1 or конец <= начало:
            raise ИИНедоступен("в ответе нет JSON-объекта")
        try:
            return json.loads(текст[начало : конец + 1])
        except ValueError as e:
            raise ИИНедоступен(f"JSON не разобрался: {e}") from e
