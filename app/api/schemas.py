"""Схемы запросов и ответов JSON-API (/hog/...).

FastAPI строит на них три вещи сразу:
- проверку входных данных: неверный JSON отклоняется с кодом 422 ещё до
  того, как запрос дойдёт до нашей логики;
- фильтр ответа: наружу уходят только объявленные поля;
- документацию: схемы видны в /hog/docs (Swagger UI).

Имена классов и полей здесь английские, в отличие от остального кода: это
внешний контракт. Поля — ключи JSON для фронтенда, классы — названия схем в
OpenAPI, а генератор схемы пропускает в имя только латиницу.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --- входной тест ---

Experience = Literal["", "none", "other", "python"]


class QuestionAnswer(BaseModel):
    id: str = Field(max_length=16, description="Код вопроса из банка, например E1")
    answer: str = Field(default="", max_length=500)


class TestSubmit(BaseModel):
    """Тело POST /hog/test/submit."""

    answers: list[QuestionAnswer] = Field(default_factory=list, max_length=20)
    experience: Experience = Field(
        default="",
        description="Программировал ли раньше: none — нет, other — на другом языке, python — на Python",
    )


class TestQuestion(BaseModel):
    id: str
    difficulty: str
    topic: str
    text: str
    code: str = ""
    options: list[str]


class TestNextStage(BaseModel):
    done: Literal[False] = False
    questions: list[TestQuestion]
    progress: int


class AnswerExplanation(BaseModel):
    id: str
    correct: bool
    text: str


class TestResult(BaseModel):
    done: Literal[True] = True
    from_zero: bool
    level: str
    level_label: str
    correct: int
    total: int
    weak_topics: list[str]
    explanations: list[AnswerExplanation]


# --- задания ---

class TaskAnswer(BaseModel):
    """Тело POST /hog/task/{id}/check: answer — для тестов и «угадай вывод», code — для задач на код."""

    answer: str = Field(default="", max_length=2000)
    code: str = Field(default="", max_length=20000)


class HintRequest(BaseModel):
    """Тело POST /hog/task/{id}/hint."""

    code: str = Field(default="", max_length=20000)


class CallCheck(BaseModel):
    call: str
    expected: Any = None
    got: Any = None
    passed: bool
    error: str = ""


class MedalOut(BaseModel):
    icon: str
    title: str
    description: str


class MemeOut(BaseModel):
    url: str
    caption: str


class LessonReward(BaseModel):
    coins: int
    xp: int
    streak: int
    spins: int
    capped: bool
    medals: list[MedalOut]
    meme: MemeOut | None = None


class TaskResult(BaseModel):
    correct: bool
    output: str
    error: str
    checks: list[CallCheck]
    explanation: str
    hint: str
    lesson_done: LessonReward | None = None


class HintOut(BaseModel):
    hint: str
    source: str = Field(description="static — из задания, иначе название модели ИИ")


# --- колесо ---

class WheelSector(BaseModel):
    coins: int
    weight: int


class WheelState(BaseModel):
    spins: int
    coins: int
    sectors: list[WheelSector]


class WheelSpin(BaseModel):
    sector: int
    coins_won: int
    coins: int
    spins_left: int


# --- магазин ---

class PurchaseOut(BaseModel):
    ok: bool = True
    coins: int
    equipped: bool
    slot: str
    asset: str


class EquipOut(BaseModel):
    ok: bool = True
    equipped: bool
    slot: str
    asset: str


# --- служебное ---

class ErrorOut(BaseModel):
    """Так выглядит любой отказ: {"detail": "текст для пользователя"}."""

    detail: str


class HealthOut(BaseModel):
    status: str
    version: str
    ai: bool
