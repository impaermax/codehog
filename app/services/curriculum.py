"""Course skeleton: vetted topics for each level.

The model does not invent the structure, it fills a predefined skeleton.
That keeps the course coherent even with a cheap model, and when the model
fails, a fallback lesson is used instead.

Topic titles, goals and concepts are learner-facing content and stay in Russian.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Level


@dataclass(frozen=True)
class LessonTopic:
    title: str
    goal: str
    concepts: tuple[str, ...]


@dataclass(frozen=True)
class CourseModule:
    title: str
    description: str
    lessons: tuple[LessonTopic, ...]


# Intro module for those who have never programmed. It goes before the
# beginner course only when the learner answered "never programmed" before
# the test. It explains what a program is with everyday examples, before
# variables and conditions appear. There is no keyboard input: input() is
# forbidden in the sandbox, and tasks are checked without a human.
MODULE_FROM_ZERO = CourseModule(
    "Что такое программа",
    "Первые шаги: команды, вывод на экран, ошибки",
    (
        LessonTopic(
            "Как мыслит компьютер",
            "Понять, что программа — это список команд, которые выполняются по порядку, "
            "как рецепт. Объяснять на бытовых примерах, без терминов",
            ("команды", "порядок выполнения"),
        ),
        LessonTopic(
            "Первая команда print",
            "Вывести на экран слова и числа. Считать яблоки: print(3 + 2). "
            "Отличать текст в кавычках от числа",
            ("print", "строки", "числа"),
        ),
        LessonTopic(
            "Ошибки — это нормально",
            "Прочитать сообщение об ошибке и найти опечатку: забытая кавычка, "
            "скобка, неправильное имя команды",
            ("ошибки", "print"),
        ),
    ),
)

# Intro module for those who programmed in another language. Loops and
# conditions are familiar to them, Python syntax is not. The module maps
# familiar C++, C#, Java and JavaScript constructs to Python, and then the
# learner continues at their own level.
MODULE_SWITCH = CourseModule(
    "Python после другого языка",
    "Знакомые конструкции в синтаксисе Python",
    (
        LessonTopic(
            "Отступы вместо скобок",
            "Понять, что блоки в Python задаются отступом, а не фигурными скобками, "
            "и что точка с запятой в конце строки не нужна. Сравнивать с C++, Java, JS",
            ("отступы", "блоки", "print"),
        ),
        LessonTopic(
            "Переменные без объявления типа",
            "Заводить переменные без int и var, понимать динамическую типизацию, "
            "форматировать вывод через f-строки вместо printf и конкатенации",
            ("переменные", "типы", "f-строки"),
        ),
        LessonTopic(
            "for по коллекции вместо счётчика",
            "Переписывать for (int i = 0; i < n; i++) на for i in range(n) "
            "и перебирать список напрямую, без индексов",
            ("for", "range", "list"),
        ),
    ),
)

# Which intro module goes first, depending on the "have you programmed before" answer
INTRO_MODULES: dict[str, CourseModule] = {"none": MODULE_FROM_ZERO, "other": MODULE_SWITCH}

SKELETON: dict[Level, tuple[CourseModule, ...]] = {
    Level.BEGINNER: (
        CourseModule(
            "Значения и переменные",
            "Из чего состоит любая программа",
            (
                LessonTopic(
                    "Числа и арифметика",
                    "Считать выражения с int и понимать // и %",
                    ("int", "арифметика"),
                ),
                LessonTopic(
                    "Строки", "Складывать строки и брать из них символы", ("str", "индексы")
                ),
                LessonTopic(
                    "Переменные",
                    "Заводить переменные и менять их значения",
                    ("переменные", "присваивание"),
                ),
            ),
        ),
        CourseModule(
            "Условия",
            "Программа принимает решения",
            (
                LessonTopic(
                    "if и else", "Ветвить программу по условию", ("if", "else", "сравнения")
                ),
                LessonTopic(
                    "Логические операторы",
                    "Соединять условия через and, or, not",
                    ("and", "or", "not"),
                ),
                LessonTopic(
                    "Границы условий", "Не путать > и >=", ("сравнения", "граничные значения")
                ),
            ),
        ),
        CourseModule(
            "Циклы",
            "Повторяем действия",
            (
                LessonTopic("Цикл for", "Перебирать range и списки", ("for", "range")),
                LessonTopic("Цикл while", "Повторять, пока верно условие", ("while", "условия")),
                LessonTopic(
                    "break и continue", "Прерывать и пропускать шаги", ("break", "continue")
                ),
            ),
        ),
        CourseModule(
            "Коллекции",
            "Списки и словари",
            (
                LessonTopic(
                    "Списки", "Добавлять, удалять и искать элементы", ("list", "append", "in")
                ),
                LessonTopic("Словари", "Хранить пары ключ-значение", ("dict", "get", "ключи")),
                LessonTopic(
                    "Перебор коллекций", "Ходить по списку и словарю циклом", ("for", "items")
                ),
            ),
        ),
        CourseModule(
            "Функции",
            "Своя первая функция",
            (
                LessonTopic(
                    "def и return",
                    "Писать функцию, которая возвращает значение",
                    ("def", "return"),
                ),
                LessonTopic(
                    "Аргументы", "Передавать данные внутрь функции", ("аргументы", "параметры")
                ),
                LessonTopic(
                    "Мини-проект", "Собрать программу из нескольких функций", ("def", "list", "if")
                ),
            ),
        ),
    ),
    Level.INTERMEDIATE: (
        CourseModule(
            "Коллекции глубже",
            "Не только list",
            (
                LessonTopic(
                    "Генераторы списков",
                    "Заменять циклы на comprehension",
                    ("comprehension", "if"),
                ),
                LessonTopic("Множества и кортежи", "Выбирать подходящий тип", ("set", "tuple")),
                LessonTopic(
                    "Сортировка по ключу",
                    "Сортировать по своему правилу",
                    ("sorted", "key", "lambda"),
                ),
            ),
        ),
        CourseModule(
            "Изменяемость",
            "Главный источник неожиданных багов",
            (
                LessonTopic(
                    "Ссылки и копии", "Понимать, когда меняется исходный объект", ("list", "copy")
                ),
                LessonTopic(
                    "Изменяемые аргументы",
                    "Избегать ловушки со значением по умолчанию",
                    ("def", "None"),
                ),
                LessonTopic("Распаковка", "Разбирать структуры на части", ("распаковка", "tuple")),
            ),
        ),
        CourseModule(
            "Декомпозиция",
            "Код, который читают",
            (
                LessonTopic("Чистые функции", "Отделять вычисление от вывода", ("def", "return")),
                LessonTopic(
                    "Обработка ошибок", "try/except по делу", ("try", "except", "исключения")
                ),
                LessonTopic(
                    "Файлы и данные", "Читать и разбирать текстовые данные", ("файлы", "split")
                ),
            ),
        ),
        CourseModule(
            "Классы",
            "Свои типы данных",
            (
                LessonTopic(
                    "class и __init__",
                    "Заводить объекты со своим состоянием",
                    ("class", "__init__"),
                ),
                LessonTopic("Методы", "Поведение рядом с данными", ("методы", "self")),
                LessonTopic("Мини-проект", "Программа на нескольких классах", ("class", "list")),
            ),
        ),
    ),
    Level.ADVANCED: (
        CourseModule(
            "Семантика Python",
            "Как язык устроен внутри",
            (
                LessonTopic(
                    "Модель объектов", "Ссылки, идентичность, равенство", ("is", "==", "id")
                ),
                LessonTopic("Область видимости", "LEGB и замыкания", ("замыкания", "nonlocal")),
                LessonTopic(
                    "Позднее связывание",
                    "Классическая ловушка с lambda в цикле",
                    ("lambda", "замыкания"),
                ),
            ),
        ),
        CourseModule(
            "Итераторы и генераторы",
            "Ленивые вычисления",
            (
                LessonTopic(
                    "Протокол итератора", "__iter__ и __next__ своими руками", ("итераторы",)
                ),
                LessonTopic("yield", "Писать генераторы", ("yield", "генераторы")),
                LessonTopic(
                    "Одноразовость", "Почему генератор обходится один раз", ("генераторы", "sum")
                ),
            ),
        ),
        CourseModule(
            "Декораторы",
            "Функции, меняющие функции",
            (
                LessonTopic(
                    "Функция как значение",
                    "Передавать и возвращать функции",
                    ("функции", "замыкания"),
                ),
                LessonTopic("Свой декоратор", "Обернуть вызов логикой", ("декораторы", "wraps")),
                LessonTopic("Декоратор с аргументами", "Три уровня вложенности", ("декораторы",)),
            ),
        ),
        CourseModule(
            "Алгоритмы",
            "Сложность и структуры",
            (
                LessonTopic(
                    "Сложность", "Оценивать O(n) и выбирать структуру", ("сложность", "dict")
                ),
                LessonTopic(
                    "Двухуказательные приёмы", "Решать задачи за один проход", ("алгоритмы",)
                ),
                LessonTopic(
                    "Проект с тестами", "Написать модуль и проверить его", ("тесты", "assert")
                ),
            ),
        ),
    ),
}


def skeleton(level: Level, experience: str = "") -> tuple[CourseModule, ...]:
    """Course modules, preceded by an intro module when the learner needs one.

    experience = "none"  -> never programmed: MODULE_FROM_ZERO;
    experience = "other" -> programmed in another language: MODULE_SWITCH;
    otherwise there is no intro module.
    """
    modules = SKELETON.get(level, SKELETON[Level.BEGINNER])
    intro = INTRO_MODULES.get(experience)
    return (intro, *modules) if intro else modules


def all_modules(level: Level) -> tuple[CourseModule, ...]:
    """Every module that may appear in a course of this level, used to look up topics."""
    return (*INTRO_MODULES.values(), *SKELETON.get(level, SKELETON[Level.BEGINNER]))
