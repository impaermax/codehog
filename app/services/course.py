"""Сборка персонального курса и наполнение уроков заданиями.

Каркас курса — наш, проверенный. Модель наполняет один урок за вызов и обязана
вернуть строгий JSON. Всё, что она вернула, проверяется: структура, типы заданий
и, для задач на код, реальный прогон эталонного решения в песочнице.
Не прошло проверку — берётся шаблонный урок, и человек ничего не теряет.
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Course, Lesson, Module, Task, User, Уровень, ТипЗадания
from app.services.ai import ИИНедоступен, КлиентИИ
from app.services.curriculum import МодульКурса, ТемаУрока, каркас
from app.services.sandbox import Песочница

лог = logging.getLogger("codehog.course")

СИСТЕМНЫЙ = (
    "Ты создаёшь один урок Python 3 для тренажёра CodeHog. "
    "Отвечаешь только одним JSON-объектом, без markdown и текста вокруг. "
    "Объяснения по-русски, код и идентификаторы латиницей."
)

ШАБЛОН_ЗАПРОСА = """Собери один урок по теме «{тема}».

Учебная цель: {цель}
Уровень ученика: {уровень}
Разрешённые понятия: {понятия}
Слабые места ученика: {слабые}

ПРАВИЛА
1. Ровно 3 задания: сначала predict (что выведет код), затем quiz (выбор),
   затем code (написать функцию solve). Именно в этом порядке.
2. Не используй импорты, input, eval, exec, файлы, сеть и случайность.
3. В задании code функция обязана называться solve.
4. tests — ровно 3 проверки вида {{"call": "solve(...)", "expect": значение}}.
   В expect только числа, строки, булевы значения, null и списки из них.
5. reference_solution обязано проходить все свои tests.
5а. В КОДЕ пиши Python-литералы: True, False, None.
    JSON-овские true, false, null внутри кода — ошибка, код не запустится.
6. theory — до 600 символов, по-русски, с одним коротким примером кода.

ФОРМАТ ОТВЕТА
{{
  "title": "Короткое название урока",
  "theory": "Объяснение",
  "tasks": [
    {{"type": "predict", "prompt": "Что выведет код?", "code": "...",
      "answer": "точный вывод", "hint": "подсказка", "explanation": "почему"}},
    {{"type": "quiz", "prompt": "Вопрос", "code": "",
      "options": ["a", "b", "c", "d"], "answer": "правильный вариант целиком",
      "hint": "подсказка", "explanation": "почему"}},
    {{"type": "code", "prompt": "Что нужно написать", "starter_code": "def solve(...):\\n    ...",
      "reference_solution": "def solve(...):\\n    return ...",
      "tests": [{{"call": "solve(1)", "expect": 1}}],
      "hint": "подсказка", "explanation": "разбор"}}
  ]
}}"""


class ПроверкаУрока:
    """Валидация того, что вернула модель. Молча ничего не чиним — отбраковываем."""

    ТИПЫ = {"predict": ТипЗадания.ВЫВОД, "quiz": ТипЗадания.ВЫБОР, "code": ТипЗадания.КОД}

    def __init__(self) -> None:
        self.песочница = Песочница(таймаут=5.0)

    def проверить(self, данные: dict) -> tuple[bool, str]:
        if not isinstance(данные, dict):
            return False, "ответ не объект"
        if not str(данные.get("title", "")).strip():
            return False, "нет заголовка"
        задания = данные.get("tasks")
        if not isinstance(задания, list) or len(задания) < 2:
            return False, "нужно минимум два задания"

        for i, з in enumerate(задания, 1):
            if not isinstance(з, dict):
                return False, f"задание {i} не объект"
            тип = з.get("type")
            if тип not in self.ТИПЫ:
                return False, f"задание {i}: неизвестный тип {тип!r}"
            if not str(з.get("prompt", "")).strip():
                return False, f"задание {i}: пустая формулировка"
            if тип == "quiz":
                варианты = з.get("options") or []
                if len(варианты) < 2:
                    return False, f"задание {i}: мало вариантов"
                if з.get("answer") not in варианты:
                    return False, f"задание {i}: правильного варианта нет в списке"
            if тип == "predict" and not str(з.get("code", "")).strip():
                return False, f"задание {i}: нет кода"
            if тип == "code":
                ок, почему = self._проверить_код(з)
                if not ок:
                    return False, f"задание {i}: {почему}"
        return True, ""

    def _проверить_код(self, задание: dict) -> tuple[bool, str]:
        эталон = str(задание.get("reference_solution", "")).strip()
        тесты = задание.get("tests") or []
        if not эталон:
            return False, "нет эталонного решения"
        if not isinstance(тесты, list) or not тесты:
            return False, "нет тестов"
        for т in тесты:
            if not isinstance(т, dict) or "call" not in т or "expect" not in т:
                return False, "тест неверного формата"
        результат = self.песочница.запустить(эталон, тесты)
        if not результат.passed:
            return False, f"эталон не проходит свои тесты ({результат.сводка})"
        return True, ""


class ГенераторКурса:
    """Создаёт курс по каркасу и наполняет уроки — моделью или шаблоном."""

    def __init__(self, сессия: Session, клиент: КлиентИИ | None = None) -> None:
        self.сессия = сессия
        self.клиент = клиент or КлиентИИ()
        self.проверка = ПроверкаУрока()

    def создать(self, юзер: User, слабые_темы: list[str] | None = None) -> Course:
        """Строит структуру курса. Задания появляются при открытии урока."""
        структура = каркас(юзер.level)
        курс = Course(
            user_id=юзер.id,
            title=f"Python: маршрут «{юзер.level.подпись}»",
            summary=self._описание(юзер.level, слабые_темы or []),
            level=юзер.level,
            generated_by="skeleton",
        )
        self.сессия.add(курс)
        self.сессия.flush()

        for i, модуль in enumerate(структура):
            м = Module(course_id=курс.id, order_index=i, title=модуль.название,
                       description=модуль.описание)
            self.сессия.add(м)
            self.сессия.flush()
            for j, тема in enumerate(модуль.уроки):
                self.сессия.add(Lesson(
                    module_id=м.id, order_index=j, title=тема.название,
                    theory="", xp_reward=20, coin_reward=10,
                ))
        self.сессия.commit()

        # первый урок наполняем шаблоном прямо сейчас: старт должен быть мгновенным,
        # а генерация моделью занимает до 25 секунд
        первый = курс.все_уроки[0] if курс.все_уроки else None
        if первый is not None and not первый.tasks:
            тема = self._тема_урока(первый, юзер.level)
            данные = запасной_урок(тема, юзер.level)
            первый.theory = данные["theory"]
            for i, з in enumerate(данные["tasks"]):
                первый.tasks.append(self._собрать_задание(з, i))
            self.сессия.commit()
        return курс

    @staticmethod
    def _описание(уровень: Уровень, слабые: list[str]) -> str:
        основа = {
            Уровень.НОВИЧОК: "Начинаем с самых основ: переменные, условия, циклы и первые функции.",
            Уровень.СРЕДНИЙ: "Базу вы знаете. Разберём коллекции, изменяемость, ошибки и классы.",
            Уровень.ПРОДВИНУТЫЙ: "Идём вглубь языка: замыкания, генераторы, декораторы и сложность.",
        }[уровень]
        if слабые:
            основа += f" Отдельное внимание темам: {', '.join(слабые)}."
        return основа

    def наполнить_урок(self, урок: Lesson, юзер: User, слабые: list[str] | None = None) -> Lesson:
        """Создаёт задания урока. Идемпотентно и устойчиво к гонке двух процессов."""
        if урок.tasks:
            return урок

        тема = self._тема_урока(урок, юзер.level)
        данные, источник = None, "template"

        if self.клиент.доступен:
            try:
                данные = self._спросить_модель(тема, юзер.level, слабые or [])
                источник = self.клиент and "ai"
            except (ИИНедоступен, Exception) as e:
                лог.warning("урок %s: модель не дала результат (%s)", урок.id, str(e)[:120])
                данные = None

        if данные is None:
            данные = запасной_урок(тема, юзер.level)
            источник = "template"

        # пока мы ходили к модели, урок мог наполнить другой процесс
        self.сессия.refresh(урок)
        if урок.tasks:
            лог.info("урок %s уже наполнен другим процессом — пропускаю", урок.id)
            return урок

        урок.title = данные.get("title") or урок.title
        урок.theory = данные.get("theory", "")
        for i, з in enumerate(данные.get("tasks", [])):
            урок.tasks.append(self._собрать_задание(з, i))
        try:
            self.сессия.commit()
        except IntegrityError:
            # уникальный индекс не дал задвоить — значит, кто-то успел раньше
            self.сессия.rollback()
            self.сессия.refresh(урок)
            лог.info("урок %s наполнен параллельно, свою копию отбросил", урок.id)
            return урок
        лог.info("урок %s наполнен (%s), заданий: %s", урок.id, источник, len(урок.tasks))
        return урок

    def _спросить_модель(self, тема: ТемаУрока, уровень: Уровень, слабые: list[str]) -> dict | None:
        запрос = ШАБЛОН_ЗАПРОСА.format(
            тема=тема.название, цель=тема.цель, уровень=уровень.подпись,
            понятия=", ".join(тема.понятия),
            слабые=", ".join(слабые) if слабые else "не выявлены",
        )
        for попытка in (1, 2):
            ответ = self.клиент.спросить(СИСТЕМНЫЙ, запрос, максимум_токенов=2500, температура=0.3)
            try:
                данные = self.клиент.достать_json(ответ.текст)
            except ИИНедоступен as e:
                лог.warning("попытка %s: %s", попытка, e)
                continue
            ок, почему = self.проверка.проверить(данные)
            if ок:
                return данные
            лог.warning("попытка %s отбракована: %s", попытка, почему)
        return None

    @staticmethod
    def _собрать_задание(сырое: dict, порядок: int) -> Task:
        тип = ПроверкаУрока.ТИПЫ.get(сырое.get("type"), ТипЗадания.ВЫВОД)
        задание = Task(
            order_index=порядок, kind=тип,
            prompt=сырое.get("prompt", ""), hint=сырое.get("hint", ""),
            starter_code=сырое.get("starter_code", "") or сырое.get("code", ""),
            solution=сырое.get("reference_solution", "") or сырое.get("explanation", ""),
            answer=str(сырое.get("answer", "")),
        )
        if тип == ТипЗадания.КОД:
            задание.проверки = сырое.get("tests", [])
        if тип == ТипЗадания.ВЫБОР:
            задание.варианты = сырое.get("options", [])
        return задание

    @staticmethod
    def _тема_урока(урок: Lesson, уровень: Уровень) -> ТемаУрока:
        структура = каркас(уровень)
        индекс_модуля = урок.module.order_index
        if индекс_модуля < len(структура):
            модуль: МодульКурса = структура[индекс_модуля]
            if урок.order_index < len(модуль.уроки):
                return модуль.уроки[урок.order_index]
        return ТемаУрока(урок.title, урок.title, ("python",))


def запасной_урок(тема: ТемаУрока, уровень: Уровень) -> dict:
    """Гарантированно рабочий урок на случай, когда модель недоступна."""
    return {
        "title": тема.название,
        "theory": (
            f"**{тема.название}.** {тема.цель}.\n\n"
            f"Ключевые понятия: {', '.join(тема.понятия)}.\n\n"
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
                "prompt": "Напишите функцию solve(numbers), которая вернёт сумму чётных чисел списка.",
                "starter_code": "def solve(numbers):\n    # ваш код\n    return 0",
                "reference_solution": "def solve(numbers):\n    return sum(n for n in numbers if n % 2 == 0)",
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
