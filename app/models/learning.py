"""Учебная часть: тест на уровень, курс, модули, уроки, задачи и решения."""
from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ВременнЫеМетки, сейчас
from app.models.user import Уровень

if TYPE_CHECKING:
    from app.models.user import User


class ТипЗадания(str, enum.Enum):
    """Разные типы, чтобы курс не был однообразным."""

    КОД = "code"            # написать функцию, проверяется тестами
    ВЫБОР = "quiz"          # выбрать правильный вариант
    ВЫВОД = "predict"       # что напечатает этот код
    ПОРЯДОК = "order"       # расставить строки в правильном порядке
    ПОЧИНИ = "debug"        # найти и исправить ошибку в готовом коде


class JSONПоле:
    """Хелпер: хранить структуру в TEXT и не думать о сериализации."""

    @staticmethod
    def прочитать(сырое: str | None, дефолт: Any) -> Any:
        if not сырое:
            return дефолт
        try:
            return json.loads(сырое)
        except (ValueError, TypeError):
            return дефолт

    @staticmethod
    def записать(значение: Any) -> str:
        return json.dumps(значение, ensure_ascii=False)


class TestAttempt(Base):
    """Прохождение входного теста. Пишется и для анонимов — до регистрации."""

    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_token: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    determined_level: Mapped[Уровень | None] = mapped_column(
        Enum(Уровень, values_callable=lambda e: [x.value for x in e]), nullable=True
    )
    # Опыт до начала курса — ответ на вопрос перед тестом:
    # "none" — никогда не программировал, "other" — писал на другом языке,
    # "python" — уже пишет на Python. Пусто у попыток, сделанных до появления вопроса.
    experience: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="test_attempts")

    @property
    def ответы(self) -> list[dict]:
        return JSONПоле.прочитать(self.answers_json, [])

    @ответы.setter
    def ответы(self, значение: list[dict]) -> None:
        self.answers_json = JSONПоле.записать(значение)

    @property
    def доля_верных(self) -> float:
        return self.correct_count / self.total_count if self.total_count else 0.0


class Course(Base, ВременнЫеМетки):
    """Персональный курс, собранный под результат теста."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    level: Mapped[Уровень] = mapped_column(
        Enum(Уровень, values_callable=lambda e: [x.value for x in e]), nullable=False
    )
    generated_by: Mapped[str] = mapped_column(String(64), default="template", nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="courses")
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Module.order_index"
    )

    @property
    def все_уроки(self) -> list["Lesson"]:
        return [у for м in self.modules for у in м.lessons]

    @property
    def прогресс(self) -> int:
        """Процент пройденного курса."""
        уроки = self.все_уроки
        if not уроки:
            return 0
        готово = sum(1 for у in уроки if у.is_completed)
        return round(готово * 100 / len(уроки))

    @property
    def открытые_уроки(self) -> set[int]:
        """Идентификаторы уроков, доступных прямо сейчас.

        Требование 2.5: дальше нельзя, пока текущий урок не пройден.
        Открыт первый урок, любой уже пройденный (чтобы вернуться и
        перечитать), и ровно один следующий за последним пройденным.
        """
        уроки = self.все_уроки
        открыты: set[int] = set()
        for номер, урок in enumerate(уроки):
            if номер == 0 or урок.is_completed or уроки[номер - 1].is_completed:
                открыты.add(урок.id)
        return открыты


class Module(Base):
    """Раздел курса — несколько уроков на одну тему."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    course: Mapped["Course"] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order_index"
    )


class Lesson(Base):
    """Урок: короткая теория плюс несколько заданий."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    theory: Mapped[str] = mapped_column(Text, default="", nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    coin_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    module: Mapped["Module"] = relationship(back_populates="lessons")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Task.order_index"
    )


class Task(Base):
    """Одно задание внутри урока."""

    __tablename__ = "tasks"
    # два процесса могут одновременно взяться наполнять один урок (фон и запрос
    # пользователя). Уникальность пары «урок + позиция» делает задвоение невозможным.
    __table_args__ = (UniqueConstraint("lesson_id", "order_index", name="uq_task_lesson_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[ТипЗадания] = mapped_column(
        Enum(ТипЗадания, values_callable=lambda e: [x.value for x in e]),
        default=ТипЗадания.КОД,
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str] = mapped_column(Text, default="", nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    solution: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # для code: список {"call": "...", "expect": ...}; для quiz/order: варианты
    checks_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    options_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    answer: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    is_completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    lesson: Mapped["Lesson"] = relationship(back_populates="tasks")
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def проверки(self) -> list[dict]:
        return JSONПоле.прочитать(self.checks_json, [])

    @проверки.setter
    def проверки(self, значение: list[dict]) -> None:
        self.checks_json = JSONПоле.записать(значение)

    @property
    def варианты(self) -> list[str]:
        return JSONПоле.прочитать(self.options_json, [])

    @варианты.setter
    def варианты(self, значение: list[str]) -> None:
        self.options_json = JSONПоле.записать(значение)


class Submission(Base):
    """Попытка решения. Храним все, чтобы видеть, где люди застревают."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=сейчас, nullable=False)

    user: Mapped["User"] = relationship(back_populates="submissions")
    task: Mapped["Task"] = relationship(back_populates="submissions")
