"""Request and response schemas of the JSON API (/hog/...).

FastAPI builds three things from them:
- input validation: malformed JSON is rejected with 422 before it reaches our code;
- response filtering: only declared fields are sent out;
- documentation: the schemas are shown in /hog/docs (Swagger UI).

Field names are the JSON keys the frontend relies on.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --- placement test ---

Experience = Literal["", "none", "other", "python"]


class QuestionAnswer(BaseModel):
    id: str = Field(max_length=16, description="Question id from the bank, e.g. E1")
    answer: str = Field(default="", max_length=500)


class TestSubmit(BaseModel):
    """Body of POST /hog/test/submit."""

    answers: list[QuestionAnswer] = Field(default_factory=list, max_length=20)
    experience: Experience = Field(
        default="",
        description="Programmed before: none — no, other — another language, python — Python",
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


# --- tasks ---


class TaskAnswer(BaseModel):
    """Body of POST /hog/task/{id}/check.

    answer is used by quiz and predict tasks, code by code tasks.
    """

    answer: str = Field(default="", max_length=2000)
    code: str = Field(default="", max_length=20000)


class HintRequest(BaseModel):
    """Body of POST /hog/task/{id}/hint."""

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
    source: str = Field(description="static for the task's own hint, otherwise the AI model name")


# --- wheel ---


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


# --- shop ---


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


# --- service ---


class ErrorOut(BaseModel):
    """Every refusal looks like this: {"detail": "message for the user"}."""

    detail: str


class HealthOut(BaseModel):
    status: str
    version: str
    ai: bool
