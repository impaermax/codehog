"""Learning data: placement test, course, modules, lessons, tasks and submissions."""

from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now
from app.models.user import Level

if TYPE_CHECKING:
    from app.models.user import User


class TaskKind(enum.StrEnum):
    """Task types, so lessons do not feel repetitive."""

    CODE = "code"  # write a function, checked by tests
    QUIZ = "quiz"  # pick the right option
    PREDICT = "predict"  # what will this code print
    ORDER = "order"  # put lines in the right order
    DEBUG = "debug"  # find and fix a bug in given code


class JSONField:
    """Helpers for storing a structure in a TEXT column."""

    @staticmethod
    def load(raw: str | None, default: Any) -> Any:
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def dump(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)


class TestAttempt(Base):
    """A placement test run. Recorded for guests too, before they sign up."""

    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_token: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    determined_level: Mapped[Level | None] = mapped_column(
        Enum(Level, values_callable=lambda e: [x.value for x in e]), nullable=True
    )
    # Prior experience, answered before the test: "none" (never programmed),
    # "other" (another language) or "python". Empty for older attempts.
    experience: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="test_attempts")

    @property
    def answers(self) -> list[dict]:
        return JSONField.load(self.answers_json, [])

    @answers.setter
    def answers(self, value: list[dict]) -> None:
        self.answers_json = JSONField.dump(value)


class Course(Base, TimestampMixin):
    """A personal course built from the placement test result."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    level: Mapped[Level] = mapped_column(
        Enum(Level, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    generated_by: Mapped[str] = mapped_column(String(64), default="template", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="courses")
    modules: Mapped[list[Module]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Module.order_index"
    )

    @property
    def all_lessons(self) -> list[Lesson]:
        return [lesson for module in self.modules for lesson in module.lessons]

    @property
    def progress(self) -> int:
        """Share of completed lessons, in percent."""
        lessons = self.all_lessons
        if not lessons:
            return 0
        done = sum(1 for lesson in lessons if lesson.is_completed)
        return round(done * 100 / len(lessons))

    @property
    def open_lessons(self) -> set[int]:
        """Ids of the lessons available right now.

        Requirement 2.5: you cannot move on until the current lesson is done.
        Open are the first lesson, every completed one (to re-read it) and
        exactly one lesson after the last completed one.
        """
        lessons = self.all_lessons
        opened: set[int] = set()
        for number, lesson in enumerate(lessons):
            if number == 0 or lesson.is_completed or lessons[number - 1].is_completed:
                opened.add(lesson.id)
        return opened


class Module(Base):
    """A course section: several lessons on one topic."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order_index"
    )


class Lesson(Base):
    """A lesson: short theory plus a few tasks."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    theory: Mapped[str] = mapped_column(Text, default="", nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    coin_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    module: Mapped[Module] = relationship(back_populates="lessons")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Task.order_index"
    )


class Task(Base):
    """A single task inside a lesson."""

    __tablename__ = "tasks"
    # Two processes may start filling the same lesson at once (the background
    # prefetch and the user's request). A unique (lesson, position) pair makes
    # duplicate tasks impossible.
    __table_args__ = (UniqueConstraint("lesson_id", "order_index", name="uq_task_lesson_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[TaskKind] = mapped_column(
        Enum(TaskKind, values_callable=lambda e: [x.value for x in e]),
        default=TaskKind.CODE,
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str] = mapped_column(Text, default="", nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    solution: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # For code tasks: a list of {"call": "...", "expect": ...}. For quizzes: the options.
    checks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    options_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    answer: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    is_completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    lesson: Mapped[Lesson] = relationship(back_populates="tasks")
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def checks(self) -> list[dict]:
        return JSONField.load(self.checks_json, [])

    @checks.setter
    def checks(self, value: list[dict]) -> None:
        self.checks_json = JSONField.dump(value)

    @property
    def options(self) -> list[str]:
        return JSONField.load(self.options_json, [])

    @options.setter
    def options(self, value: list[str]) -> None:
        self.options_json = JSONField.dump(value)


class Submission(Base):
    """A solution attempt. All attempts are kept to see where learners get stuck."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="submissions")
    task: Mapped[Task] = relationship(back_populates="submissions")
