"""Building a personal course and filling lessons with tasks.

The course skeleton is ours and vetted. The model fills one lesson per call
and must return strict JSON. Everything it returns is validated: structure,
task types and, for code tasks, an actual run of the reference solution in
the sandbox. If validation fails, a fallback lesson is used instead.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Course, Lesson, Level, Module, Submission, Task, TaskKind, User
from app.services.ai import AIClient, AIUnavailableError
from app.services.curriculum import LessonTopic, all_modules, skeleton
from app.services.ready_lessons import READY_LESSONS
from app.services.sandbox import Sandbox

logger = logging.getLogger("codehog.course")

SYSTEM_PROMPT = (
    "You create one Python 3 lesson for the CodeHogwarts trainer. "
    "Reply with a single JSON object only, without markdown or any text around it. "
    "Write all explanations in Russian; code and identifiers in English."
)

PROMPT_TEMPLATE = """Create one lesson on the topic "{topic}".

Learning goal: {goal}
Learner level: {level}
Allowed concepts: {concepts}
Learner's weak spots: {weak}

RULES
1. Exactly 3 tasks, in this order: predict (what the code prints), quiz (pick an
   option), code (write a function named solve).
2. Do not use imports, input, eval, exec, files, network or randomness.
3. In the code task the function must be called solve.
4. tests: exactly 3 checks of the form {{"call": "solve(...)", "expect": value}}.
   expect may only hold numbers, strings, booleans, null and lists of them.
5. reference_solution must pass all of its tests.
6. Inside CODE use Python literals True, False, None. JSON true, false, null
   inside code is an error: the code will not run.
7. theory: up to 600 characters, in Russian, with one short code example.

RESPONSE FORMAT
{{
  "title": "Short lesson title",
  "theory": "Explanation",
  "tasks": [
    {{"type": "predict", "prompt": "Что выведет код?", "code": "...",
      "answer": "exact output", "hint": "hint", "explanation": "why"}},
    {{"type": "quiz", "prompt": "Question", "code": "",
      "options": ["a", "b", "c", "d"], "answer": "the full correct option",
      "hint": "hint", "explanation": "why"}},
    {{"type": "code", "prompt": "What to write", "starter_code": "def solve(...):\\n    ...",
      "reference_solution": "def solve(...):\\n    return ...",
      "tests": [{{"call": "solve(1)", "expect": 1}}],
      "hint": "hint", "explanation": "walkthrough"}}
  ]
}}"""

# The opening of the course summary when an intro module comes first
COURSE_INTROS = {
    "none": "Начнём с самого начала: что такое программа, первая команда print "
    "и как читать ошибки. Дальше — ",
    "other": "Сначала переложим знакомые конструкции на синтаксис Python: отступы, "
    "переменные без типов, циклы по коллекциям. Дальше — ",
}

LEVEL_SUMMARIES = {
    Level.BEGINNER: "Начинаем с самых основ: переменные, условия, циклы и первые функции.",
    Level.INTERMEDIATE: "Базу вы знаете. Разберём коллекции, изменяемость, ошибки и классы.",
    Level.ADVANCED: "Идём вглубь языка: замыкания, генераторы, декораторы и сложность.",
}


class LessonValidator:
    """Validates what the model returned. Nothing is silently fixed: bad lessons are rejected."""

    TYPES = {"predict": TaskKind.PREDICT, "quiz": TaskKind.QUIZ, "code": TaskKind.CODE}

    def __init__(self) -> None:
        self.sandbox = Sandbox(timeout=5.0)

    def check(self, data: dict) -> tuple[bool, str]:
        """(True, "") if the lesson is usable, otherwise (False, reason)."""
        if not isinstance(data, dict):
            return False, "reply is not an object"
        if not str(data.get("title", "")).strip():
            return False, "no title"
        tasks = data.get("tasks")
        if not isinstance(tasks, list) or len(tasks) < 2:
            return False, "at least two tasks are required"

        for number, task in enumerate(tasks, 1):
            if not isinstance(task, dict):
                return False, f"task {number} is not an object"
            kind = task.get("type")
            if kind not in self.TYPES:
                return False, f"task {number}: unknown type {kind!r}"
            if not str(task.get("prompt", "")).strip():
                return False, f"task {number}: empty prompt"
            if kind == "quiz":
                options = task.get("options") or []
                if len(options) < 2:
                    return False, f"task {number}: too few options"
                if task.get("answer") not in options:
                    return False, f"task {number}: the correct option is not in the list"
            if kind == "predict" and not str(task.get("code", "")).strip():
                return False, f"task {number}: no code"
            if kind == "code":
                ok, reason = self._check_code(task)
                if not ok:
                    return False, f"task {number}: {reason}"
        return True, ""

    def _check_code(self, task: dict) -> tuple[bool, str]:
        reference = str(task.get("reference_solution", "")).strip()
        tests = task.get("tests") or []
        if not reference:
            return False, "no reference solution"
        if not isinstance(tests, list) or not tests:
            return False, "no tests"
        for test in tests:
            if not isinstance(test, dict) or "call" not in test or "expect" not in test:
                return False, "malformed test"
        result = self.sandbox.run(reference, tests)
        if not result.passed:
            return False, f"reference solution fails its own tests ({result.summary})"
        return True, ""


class CourseGenerator:
    """Builds a course from the skeleton and fills its lessons.

    Tasks come from a ready lesson, the model or the fallback template.
    """

    def __init__(self, session: Session, client: AIClient | None = None) -> None:
        self.session = session
        self.client = client or AIClient()
        self.validator = LessonValidator()

    def create(
        self, user: User, weak_topics: list[str] | None = None, experience: str = ""
    ) -> Course:
        """Build the course structure. Tasks appear when a lesson is opened.

        experience is the answer given before the test: "none" puts the
        intro module with everyday examples first, "other" puts the module
        for switching to Python from another language first.
        """
        modules = skeleton(user.level, experience)
        course = Course(
            user_id=user.id,
            title=f"Python: маршрут «{user.level.label}»",
            summary=self._with_intro(
                COURSE_INTROS.get(experience, ""), self._describe(user.level, weak_topics or [])
            ),
            level=user.level,
            generated_by="skeleton",
        )
        self.session.add(course)
        self.session.flush()

        for module_index, module in enumerate(modules):
            module_row = Module(
                course_id=course.id,
                order_index=module_index,
                title=module.title,
                description=module.description,
            )
            self.session.add(module_row)
            self.session.flush()
            for lesson_index, topic in enumerate(module.lessons):
                self.session.add(
                    Lesson(
                        module_id=module_row.id,
                        order_index=lesson_index,
                        title=topic.title,
                        theory="",
                        xp_reward=20,
                        coin_reward=10,
                    )
                )
        self.session.commit()

        # The first lesson is filled right away: the start must be instant, while
        # generation takes up to 25 seconds. Every possible first lesson has a
        # hand-written version in ready_lessons.py.
        first = course.all_lessons[0] if course.all_lessons else None
        if first is not None and not first.tasks:
            topic = self._lesson_topic(first, user.level)
            data = READY_LESSONS.get(topic.title) or fallback_lesson(topic)
            first.theory = data["theory"]
            for index, raw in enumerate(data["tasks"]):
                first.tasks.append(self._build_task(raw, index))
            self.session.commit()
        return course

    @staticmethod
    def _with_intro(intro: str, description: str) -> str:
        """Join the intro and the level summary, lowercasing the summary's first letter."""
        if not intro or not description:
            return intro + description
        return intro + description[0].lower() + description[1:]

    @staticmethod
    def _describe(level: Level, weak_topics: list[str]) -> str:
        summary = LEVEL_SUMMARIES[level]
        if weak_topics:
            summary += f" Отдельное внимание темам: {', '.join(weak_topics)}."
        return summary

    def fill_lesson(
        self, lesson: Lesson, user: User, weak_topics: list[str] | None = None
    ) -> Lesson:
        """Create the lesson's tasks. Idempotent and safe against two processes racing."""
        if lesson.tasks:
            return lesson

        topic = self._lesson_topic(lesson, user.level)
        data, source = None, "fallback"

        # A ready lesson beats a generated one: it was written and checked by hand.
        if topic.title in READY_LESSONS:
            data, source = READY_LESSONS[topic.title], "ready"
        elif self.client.available:
            try:
                data = self._ask_model(topic, user.level, weak_topics or [])
                source = "ai"
            except Exception as e:
                logger.warning("lesson %s: the model gave no result (%s)", lesson.id, str(e)[:120])
                data = None

        if data is None:
            data = fallback_lesson(topic)
            source = "fallback"

        # While we were waiting for the model, another process may have filled the lesson.
        self.session.refresh(lesson)
        if lesson.tasks:
            logger.info("lesson %s was filled by another process, skipping", lesson.id)
            return lesson

        lesson.title = data.get("title") or lesson.title
        lesson.theory = data.get("theory", "")
        for index, raw in enumerate(data.get("tasks", [])):
            lesson.tasks.append(self._build_task(raw, index))
        try:
            self.session.commit()
        except IntegrityError:
            # The unique index prevented duplicates: someone else was faster.
            self.session.rollback()
            self.session.refresh(lesson)
            logger.info("lesson %s was filled in parallel, dropped our copy", lesson.id)
            return lesson
        logger.info("lesson %s filled (%s), tasks: %s", lesson.id, source, len(lesson.tasks))
        return lesson

    def _ask_model(self, topic: LessonTopic, level: Level, weak_topics: list[str]) -> dict | None:
        prompt = PROMPT_TEMPLATE.format(
            topic=topic.title,
            goal=topic.goal,
            level=level.label,
            concepts=", ".join(topic.concepts),
            weak=", ".join(weak_topics) if weak_topics else "none found",
        )
        for attempt in (1, 2):
            reply = self.client.ask(SYSTEM_PROMPT, prompt, max_tokens=2500, temperature=0.3)
            try:
                data = self.client.extract_json(reply.text)
            except AIUnavailableError as e:
                logger.warning("attempt %s: %s", attempt, e)
                continue
            ok, reason = self.validator.check(data)
            if ok:
                return data
            logger.warning("attempt %s rejected: %s", attempt, reason)
        return None

    @staticmethod
    def _build_task(raw: dict, order: int) -> Task:
        kind = LessonValidator.TYPES.get(raw.get("type"), TaskKind.PREDICT)
        task = Task(
            order_index=order,
            kind=kind,
            prompt=raw.get("prompt", ""),
            hint=raw.get("hint", ""),
            starter_code=raw.get("starter_code", "") or raw.get("code", ""),
            solution=raw.get("reference_solution", "") or raw.get("explanation", ""),
            answer=str(raw.get("answer", "")),
        )
        if kind == TaskKind.CODE:
            task.checks = raw.get("tests", [])
        if kind == TaskKind.QUIZ:
            task.options = raw.get("options", [])
        return task

    @staticmethod
    def _lesson_topic(lesson: Lesson, level: Level) -> LessonTopic:
        # Look the module up by title first. The index does not work: in a
        # course with an intro module that module comes first and shifts the rest.
        for module in all_modules(level):
            if module.title == lesson.module.title and lesson.order_index < len(module.lessons):
                return module.lessons[lesson.order_index]
        # Fallback for courses built before intro modules existed
        modules = skeleton(level)
        module_index = lesson.module.order_index
        if module_index < len(modules) and lesson.order_index < len(modules[module_index].lessons):
            return modules[module_index].lessons[lesson.order_index]
        return LessonTopic(lesson.title, lesson.title, ("python",))


# The code task of the old generic template. It identifies lessons built before
# ready lessons existed: their tasks have nothing to do with the lesson topic.
_OLD_TEMPLATE_PROMPT = "Напишите функцию solve(numbers), которая вернёт сумму чётных чисел списка."


def reset_template_lessons(session: Session) -> int:
    """Clear unfinished lessons that still hold the old generic tasks.

    A lesson without tasks is filled again when opened: with a ready lesson
    if there is one, otherwise by the model. Completed lessons are left alone,
    they are the learner's history. Safe to call repeatedly.
    """
    lessons = (
        session.scalars(
            select(Lesson)
            .join(Task)
            .where(Lesson.is_completed.is_(False), Task.prompt == _OLD_TEMPLATE_PROMPT)
        )
        .unique()
        .all()
    )
    for lesson in lessons:
        task_ids = [task.id for task in lesson.tasks]
        session.execute(delete(Submission).where(Submission.task_id.in_(task_ids)))
        lesson.tasks.clear()
        lesson.theory = ""
    session.commit()
    return len(lessons)


def fallback_lesson(topic: LessonTopic) -> dict:
    """A lesson that always works, for when the model is unavailable."""
    # The skeleton goal is also written for the model, so after the first
    # sentence it may contain instructions for it. The learner does not need them.
    goal = topic.goal.split(". ")[0].rstrip(".")
    return {
        "title": topic.title,
        "theory": (
            f"**{topic.title}.** {goal}.\n\n"
            f"Ключевые понятия: {', '.join(topic.concepts)}.\n\n"
            "Разберите пример ниже и решите задание — этого достаточно, "
            "чтобы двинуться дальше."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет этот код?",
                "code": "values = [3, 1, 2]\nvalues.sort()\nprint(values)",
                "answer": "[1, 2, 3]",
                "hint": "sort меняет список на месте.",
                "explanation": "Метод sort сортирует список и ничего не возвращает.",
            },
            {
                "type": "quiz",
                "prompt": "Что вернёт функция без явного return?",
                "code": "def f():\n    x = 1",
                "options": ["None", "0", "1", "ошибку"],
                "answer": "None",
                "hint": "В Python у любой функции есть возвращаемое значение.",
                "explanation": "Без return функция возвращает None.",
            },
            {
                "type": "code",
                "prompt": _OLD_TEMPLATE_PROMPT,
                "starter_code": "def solve(numbers):\n    # ваш код\n    return 0",
                "reference_solution": (
                    "def solve(numbers):\n    return sum(n for n in numbers if n % 2 == 0)"
                ),
                "tests": [
                    {"call": "solve([1, 2, 3, 4])", "expect": 6},
                    {"call": "solve([])", "expect": 0},
                    {"call": "solve([1, 3, 5])", "expect": 0},
                ],
                "hint": "Проверяйте остаток от деления на 2.",
                "explanation": "Фильтруем чётные и складываем через sum.",
            },
        ],
    }
