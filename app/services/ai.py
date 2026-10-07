"""Client for the ExperientialLabs gateway. It is OpenAI-compatible, so requests are simple.

The key point: the app must work without an API key. When there is no key or
the model is unavailable, the caller falls back to template lessons, and the
learner does not notice.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("codehog.ai")


class AIUnavailableError(Exception):
    """The model did not answer, or answered with garbage."""


@dataclass
class AIReply:
    text: str
    model: str
    cost: float = 0.0
    tokens: int = 0


class AIClient:
    """A thin wrapper over /chat/completions with a fallback model."""

    def __init__(self, timeout: float = 90.0) -> None:
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return settings.ai_enabled

    def ask(
        self,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 3000,
        temperature: float = 0.4,
    ) -> AIReply:
        if not self.available:
            raise AIUnavailableError("EXPLABS_API_KEY is not set")

        models = [model or settings.course_model, settings.fallback_model]
        last_error = "unknown"
        for name in models:
            try:
                return self._call(name, system, prompt, max_tokens, temperature)
            except Exception as e:
                last_error = str(e)[:200]
                logger.warning("model %s did not answer: %s", name, last_error)
        raise AIUnavailableError(last_error)

    def _call(
        self, model: str, system: str, prompt: str, max_tokens: int, temperature: float
    ) -> AIReply:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{settings.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.api_key}"},
                json=body,
            )
        if response.status_code != 200:
            raise AIUnavailableError(f"HTTP {response.status_code}: {response.text[:200]}")
        data = response.json()
        if "error" in data:
            raise AIUnavailableError(data["error"].get("message", "gateway error"))
        text = data["choices"][0]["message"].get("content") or ""
        if not text.strip():
            raise AIUnavailableError("empty model reply")
        usage = data.get("usage", {}) or {}
        return AIReply(
            text=text,
            model=model,
            cost=float(usage.get("cost", 0) or 0),
            tokens=int(usage.get("total_tokens", 0) or 0),
        )

    @staticmethod
    def extract_json(text: str) -> dict:
        """Models like to wrap JSON in explanations and ``` blocks. Pull the object out."""
        text = text.strip()
        block = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
        if block:
            text = block.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise AIUnavailableError("no JSON object in the reply")
        try:
            return json.loads(text[start : end + 1])
        except ValueError as e:
            raise AIUnavailableError(f"could not parse JSON: {e}") from e
