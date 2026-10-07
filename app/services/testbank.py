"""Placement test: the question bank and adaptive question order.

First come three medium questions. Weak results lead to three easy ones and
the beginner level. Good results lead to three hard ones, which separate the
intermediate and advanced levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Level

EASY, MEDIUM, HARD = "easy", "medium", "hard"


@dataclass(frozen=True)
class Question:
    """A single test question. The answer stays on the server."""

    id: str
    difficulty: str
    topic: str
    text: str
    code: str = ""
    options: list[str] = field(default_factory=list)
    answer: str = ""
    explanation: str = ""

    def to_client(self) -> dict:
        """The question without its answer, as sent to the browser."""
        return {
            "id": self.id,
            "difficulty": self.difficulty,
            "topic": self.topic,
            "text": self.text,
            "code": self.code,
            "options": self.options,
        }


BANK: list[Question] = [
    Question(
        "E1",
        EASY,
        "арифметика",
        "Что выведет этот код?",
        "x = 7\nprint(x // 2)",
        ["3", "3.5", "4", "1"],
        "3",
        "Два слэша — целочисленное деление: дробная часть отбрасывается.",
    ),
    Question(
        "E2",
        EASY,
        "списки",
        "Что выведет этот код?",
        'items = ["a", "b", "c"]\nprint(items[1])',
        ["b", "a", "c", "ошибка"],
        "b",
        "Индексы начинаются с нуля, поэтому items[1] — второй элемент.",
    ),
    Question(
        "E3",
        EASY,
        "условия",
        "Какой оператор поставить, чтобы условие выполнялось для совершеннолетних?",
        "if age __ 18:\n    print('можно')",
        [">=", ">", "==", "<="],
        ">=",
        "Совершеннолетние — это 18 и больше, значит нужно «больше или равно».",
    ),
    Question(
        "M1",
        MEDIUM,
        "генераторы списков",
        "Что выведет этот код?",
        "print([x * x for x in range(5) if x % 2 == 0])",
        ["[0, 4, 16]", "[0, 1, 4, 9, 16]", "[4, 16]", "[0, 2, 4]"],
        "[0, 4, 16]",
        "Берутся только чётные 0, 2, 4 — и возводятся в квадрат.",
    ),
    Question(
        "M2",
        MEDIUM,
        "словари",
        "Что выведет этот код?",
        'd = {"a": 2}\nd["b"] = d.get("b", 0) + 1\nprint(d["b"])',
        ["1", "0", "2", "KeyError"],
        "1",
        "Ключа b ещё нет, get вернёт 0, к нему прибавляется единица.",
    ),
    Question(
        "M3",
        MEDIUM,
        "изменяемость",
        "Что выведет этот код?",
        "def add_one(xs):\n    xs.append(1)\n\na = [0]\nr = add_one(a)\nprint(a, r)",
        ["[0, 1] None", "[0] None", "[0, 1] [0, 1]", "[0] [0, 1]"],
        "[0, 1] None",
        "Список меняется на месте, а функция без return возвращает None.",
    ),
    Question(
        "H1",
        HARD,
        "аргументы по умолчанию",
        "Что выведет этот код?",
        "def f(x, acc=[]):\n    acc.append(x)\n    return len(acc)\n\nprint(f(1), f(2))",
        ["1 2", "1 1", "2 2", "ошибка"],
        "1 2",
        "Список по умолчанию создаётся один раз и живёт между вызовами.",
    ),
    Question(
        "H2",
        HARD,
        "замыкания",
        "Что выведет этот код?",
        "fs = [lambda: i for i in range(3)]\nprint([f() for f in fs])",
        ["[2, 2, 2]", "[0, 1, 2]", "[3, 3, 3]", "[0, 0, 0]"],
        "[2, 2, 2]",
        "Замыкание держит саму переменную, а не её значение на момент создания.",
    ),
    Question(
        "H3",
        HARD,
        "генераторы",
        "Что выведет этот код?",
        "g = (x * x for x in range(3))\nprint(sum(g), sum(g))",
        ["5 0", "5 5", "0 5", "ошибка"],
        "5 0",
        "Генератор обходится один раз: второй sum получает уже пустую последовательность.",
    ),
]

BY_ID = {question.id: question for question in BANK}


def by_difficulty(difficulty: str) -> list[Question]:
    return [question for question in BANK if question.difficulty == difficulty]


class AdaptiveTest:
    """Walks a learner through the test branches and determines the final level."""

    FIRST_STAGE = [question.id for question in by_difficulty(MEDIUM)]

    @staticmethod
    def first_questions() -> list[Question]:
        return by_difficulty(MEDIUM)

    @staticmethod
    def next_stage(answers: list[dict]) -> list[Question]:
        """What to show after the three medium questions. An empty list ends the test."""
        medium = [a for a in answers if a["id"] in AdaptiveTest.FIRST_STAGE]
        if len(medium) < 3:
            return []
        correct = sum(1 for a in medium if a["correct"])
        asked = {a["id"] for a in answers}
        candidates = by_difficulty(EASY) if correct <= 1 else by_difficulty(HARD)
        return [question for question in candidates if question.id not in asked]

    @staticmethod
    def determine_level(answers: list[dict]) -> Level:
        medium_correct = sum(1 for a in answers if a["id"].startswith("M") and a["correct"])
        hard_correct = sum(1 for a in answers if a["id"].startswith("H") and a["correct"])
        if medium_correct <= 1:
            return Level.BEGINNER
        if hard_correct >= 2:
            return Level.ADVANCED
        return Level.INTERMEDIATE

    @staticmethod
    def weak_topics(answers: list[dict]) -> list[str]:
        """Topics of the questions answered incorrectly."""
        return sorted(
            {BY_ID[a["id"]].topic for a in answers if not a["correct"] and a["id"] in BY_ID}
        )
