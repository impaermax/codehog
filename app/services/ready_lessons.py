"""Hand-written lessons.

Generating a lesson with the model takes up to 25 seconds, so the first lesson
of a course is filled right away without it. It used to come from one generic
template, and a learner who had never seen code first got a task about summing
the even numbers of a list.

These are the lessons a course can start with: both intro modules in full and
the first lesson of every level. Intro modules are never sent to the model:
they are read by people who have never programmed, so their tasks must be vetted.

The key is the topic title from curriculum.py. The format matches the model's
reply and passes the same validation: every code task's reference solution is run.
Lesson texts are learner-facing content and stay in Russian.
"""

from __future__ import annotations

READY_LESSONS: dict[str, dict] = {
    # --- intro module "What is a program" ---
    "Как мыслит компьютер": {
        "title": "Как мыслит компьютер",
        "theory": (
            "**Программа — это рецепт.** Компьютер не догадывается, чего ты хочешь: "
            "он выполняет команды строго по очереди, сверху вниз, ровно так, как написано.\n\n"
            "Команда `print` выводит текст на экран. Программа из трёх команд:\n"
            '`print("Налить воду")`\n`print("Вскипятить")`\n`print("Заварить чай")`\n\n'
            "Поменяешь строки местами — и чай заварится раньше, чем закипит вода."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет программа?",
                "code": 'print("Привет, мир")',
                "answer": "Привет, мир",
                "hint": "Кавычки на экран не выводятся — только то, что внутри них.",
                "explanation": "print показывает текст из кавычек без самих кавычек.",
            },
            {
                "type": "quiz",
                "prompt": "В каком порядке компьютер выполняет команды?",
                "code": "",
                "options": [
                    "Сверху вниз, по очереди",
                    "В случайном порядке",
                    "Сначала самые важные",
                    "Снизу вверх",
                ],
                "answer": "Сверху вниз, по очереди",
                "hint": "Вспомни рецепт: шаги идут один за другим.",
                "explanation": "Команды выполняются по порядку, начиная с первой строки.",
            },
            {
                "type": "code",
                "prompt": "Рецепт перепутан. Расставь шаги в правильном порядке: "
                "сначала налить воду, потом вскипятить, потом заварить.",
                "starter_code": (
                    'def solve():\n    return ["заварить", "налить воду", "вскипятить"]'
                ),
                "reference_solution": (
                    'def solve():\n    return ["налить воду", "вскипятить", "заварить"]'
                ),
                "tests": [
                    {"call": "solve()", "expect": ["налить воду", "вскипятить", "заварить"]}
                ],
                "hint": "Меняй местами только слова в кавычках, остальное не трогай.",
                "explanation": (
                    "Порядок важен: компьютер выполнит шаги ровно так, как они записаны."
                ),
            },
        ],
    },
    "Первая команда print": {
        "title": "Первая команда print",
        "theory": (
            "`print` выводит на экран то, что стоит в скобках.\n\n"
            '**Текст** пишется в кавычках: `print("кот")` покажет кот.\n'
            "**Числа** пишутся без кавычек, и с ними можно считать: `print(3 + 2)` покажет 5.\n\n"
            'Кавычки меняют смысл: `print("3 + 2")` покажет 3 + 2 — это уже просто текст, '
            "компьютер его не считает."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет программа?",
                "code": "print(10 - 4)",
                "answer": "6",
                "hint": "Кавычек нет — значит, это пример, и компьютер его посчитает.",
                "explanation": "Без кавычек 10 - 4 — это вычисление, результат 6.",
            },
            {
                "type": "quiz",
                "prompt": "Что выведет эта команда?",
                "code": 'print("3 + 2")',
                "options": ["3 + 2", "5", "Ошибку", "Ничего"],
                "answer": "3 + 2",
                "hint": "Посмотри на кавычки.",
                "explanation": "В кавычках — текст. Его print выводит как есть, без подсчёта.",
            },
            {
                "type": "code",
                "prompt": "У Маши 3 яблока, у Пети 4. Напиши после return пример, "
                "который посчитает, сколько яблок у них вместе.",
                "starter_code": "def solve():\n    return 0",
                "reference_solution": "def solve():\n    return 3 + 4",
                "tests": [{"call": "solve()", "expect": 7}],
                "hint": "Замени 0 на сложение двух чисел, без кавычек.",
                "explanation": "3 + 4 без кавычек — вычисление, получится 7.",
            },
        ],
    },
    "Ошибки — это нормально": {
        "title": "Ошибки — это нормально",
        "theory": (
            "Ошибки бывают у всех, даже у опытных программистов. Python не ругается, "
            "а подсказывает: читай **последнюю строку** сообщения.\n\n"
            "**SyntaxError** — запись сломана: забыта кавычка или скобка. "
            'Пример: `print("привет)`\n'
            "**NameError** — такого имени Python не знает, чаще всего это опечатка. "
            'Пример: `prnt("привет")`\n\n'
            "Нашёл строку из сообщения, исправил опечатку — запускай снова."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Эта программа без ошибок. Что она выведет?",
                "code": 'print("Ошибки", "это нормально")',
                "answer": "Ошибки это нормально",
                "hint": "Если в print несколько частей через запятую, между ними ставится пробел.",
                "explanation": "print выводит все части по порядку и разделяет их пробелом.",
            },
            {
                "type": "quiz",
                "prompt": "Какую ошибку покажет Python?",
                "code": 'prnt("Привет")',
                "options": ["NameError", "SyntaxError", "ZeroDivisionError", "Ошибки не будет"],
                "answer": "NameError",
                "hint": "Запись целая, но команда написана с опечаткой.",
                "explanation": "Имени prnt Python не знает — это NameError.",
            },
            {
                "type": "code",
                "prompt": "В строке забыта закрывающая кавычка. Исправь её, "
                "чтобы функция вернула слово Привет.",
                "starter_code": 'def solve():\n    return "Привет',
                "reference_solution": 'def solve():\n    return "Привет"',
                "tests": [{"call": "solve()", "expect": "Привет"}],
                "hint": "Текст должен начинаться и заканчиваться кавычкой.",
                "explanation": (
                    "Без второй кавычки Python не понимает, где кончается текст: это SyntaxError."
                ),
            },
        ],
    },
    # --- intro module "Python after another language" ---
    "Отступы вместо скобок": {
        "title": "Отступы вместо скобок",
        "theory": (
            "В C++, Java и JavaScript блок кода ограничивают фигурные скобки. "
            "В Python их нет — блок задаётся **отступом в 4 пробела** после двоеточия.\n\n"
            'Java: `if (x > 0) { System.out.println("плюс"); }`\n'
            'Python: `if x > 0:` и на следующей строке с отступом `print("плюс")`\n\n'
            "Скобки вокруг условия не нужны, точка с запятой в конце строки тоже. "
            "Отступ здесь не оформление, а синтаксис: сдвинул строку — поменял логику."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": 'x = 1\nif x > 3:\n    print("большое")\nprint("конец")',
                "answer": "конец",
                "hint": "Какая строка внутри if, а какая — нет?",
                "explanation": 'print("большое") с отступом и выполняется только при x > 3. '
                'print("конец") без отступа, он вне if.',
            },
            {
                "type": "quiz",
                "prompt": "Чем в Python обозначается тело if?",
                "code": "",
                "options": ["Отступом", "Фигурными скобками", "Словом end", "Точкой с запятой"],
                "answer": "Отступом",
                "hint": "Фигурных скобок для блоков в Python нет.",
                "explanation": "Блок начинается после двоеточия и идёт, пока сохраняется отступ.",
            },
            {
                "type": "code",
                "prompt": (
                    'Перепиши на Python: if (n > 0) { return "плюс"; } else { return "не плюс"; }'
                ),
                "starter_code": "def solve(n):\n    # твой if/else здесь\n    pass",
                "reference_solution": 'def solve(n):\n    if n > 0:\n        return "плюс"\n'
                '    else:\n        return "не плюс"',
                "tests": [
                    {"call": "solve(5)", "expect": "плюс"},
                    {"call": "solve(0)", "expect": "не плюс"},
                    {"call": "solve(-3)", "expect": "не плюс"},
                ],
                "hint": "После if и else — двоеточие, тело каждого — с отступом.",
                "explanation": "Без скобок и точек с запятой, блоки — отступами.",
            },
        ],
    },
    "Переменные без объявления типа": {
        "title": "Переменные без объявления типа",
        "theory": (
            "В Python не пишут `int`, `var` или `let`: переменная появляется при первом "
            "присваивании, а тип определяется значением.\n\n"
            "C#: `int count = 3;` — Python: `count = 3`\n\n"
            "Текст со значениями собирают **f-строкой** вместо конкатенации и printf: "
            '`f"Привет, {name}"`. Выражение в фигурных скобках подставится в строку.'
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": 'name = "Аня"\nage = 20\nprint(f"{name}: {age}")',
                "answer": "Аня: 20",
                "hint": "Фигурные скобки в f-строке заменяются значениями переменных.",
                "explanation": "f-строка подставила name и age на свои места.",
            },
            {
                "type": "quiz",
                "prompt": "Как в Python завести переменную count со значением 3?",
                "code": "",
                "options": ["count = 3", "int count = 3", "var count = 3;", "let count = 3"],
                "answer": "count = 3",
                "hint": "Ни типа, ни ключевого слова, ни точки с запятой.",
                "explanation": "Переменная создаётся простым присваиванием.",
            },
            {
                "type": "code",
                "prompt": "Верни приветствие вида «Привет, Аня!» через f-строку.",
                "starter_code": 'def solve(name):\n    return ""',
                "reference_solution": 'def solve(name):\n    return f"Привет, {name}!"',
                "tests": [
                    {"call": 'solve("Аня")', "expect": "Привет, Аня!"},
                    {"call": 'solve("Max")', "expect": "Привет, Max!"},
                    {"call": 'solve("")', "expect": "Привет, !"},
                ],
                "hint": "Перед кавычкой поставь f, имя — в фигурных скобках.",
                "explanation": 'f"Привет, {name}!" подставляет аргумент в строку.',
            },
        ],
    },
    "for по коллекции вместо счётчика": {
        "title": "for по коллекции вместо счётчика",
        "theory": (
            "Цикл со счётчиком `for (int i = 0; i < n; i++)` в Python записывается "
            "как `for i in range(n):`. range(n) даёт числа от 0 до n - 1.\n\n"
            "Но чаще индекс вообще не нужен: список перебирают напрямую — "
            "`for item in items:`. Короче и без ошибок на единицу."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": "total = 0\nfor i in range(4):\n    total += i\nprint(total)",
                "answer": "6",
                "hint": "range(4) — это 0, 1, 2, 3.",
                "explanation": "0 + 1 + 2 + 3 = 6.",
            },
            {
                "type": "quiz",
                "prompt": "Какие числа даёт range(3)?",
                "code": "",
                "options": ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "3"],
                "answer": "0, 1, 2",
                "hint": "Начало — 0, конец не включается.",
                "explanation": "range(3) идёт от 0 до 2 включительно.",
            },
            {
                "type": "code",
                "prompt": "Верни сумму чисел списка. Перебирай список напрямую, без индексов.",
                "starter_code": (
                    "def solve(numbers):\n    total = 0\n"
                    "    # for ... in numbers:\n    return total"
                ),
                "reference_solution": "def solve(numbers):\n    total = 0\n    for n in numbers:\n"
                "        total += n\n    return total",
                "tests": [
                    {"call": "solve([1, 2, 3])", "expect": 6},
                    {"call": "solve([])", "expect": 0},
                    {"call": "solve([10, -5])", "expect": 5},
                ],
                "hint": "for n in numbers: и прибавляй n к total.",
                "explanation": "Цикл сразу отдаёт элементы списка, индекс не нужен.",
            },
        ],
    },
    # --- first lessons of each level ---
    "Числа и арифметика": {
        "title": "Числа и арифметика",
        "theory": (
            "Python считает как калькулятор: `+`, `-`, `*`, `/`.\n\n"
            "Есть ещё два действия, без которых не обойтись:\n"
            "`//` — деление нацело: `7 // 2` даёт 3;\n"
            "`%` — остаток от деления: `7 % 2` даёт 1.\n\n"
            "Остаток помогает проверить чётность: число чётное, если `n % 2` равно 0."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": "print(17 // 5)",
                "answer": "3",
                "hint": "Сколько раз 5 целиком помещается в 17?",
                "explanation": "17 // 5 = 3, остаток 2 отбрасывается.",
            },
            {
                "type": "quiz",
                "prompt": "Чему равно 10 % 3?",
                "code": "",
                "options": ["1", "3", "3.33", "0"],
                "answer": "1",
                "hint": "10 = 3 · 3 + ?",
                "explanation": "В 10 три тройки и единица в остатке.",
            },
            {
                "type": "code",
                "prompt": "В коробку помещается 6 яиц. Верни, сколько полных коробок "
                "получится из n яиц.",
                "starter_code": "def solve(n):\n    return 0",
                "reference_solution": "def solve(n):\n    return n // 6",
                "tests": [
                    {"call": "solve(12)", "expect": 2},
                    {"call": "solve(13)", "expect": 2},
                    {"call": "solve(5)", "expect": 0},
                ],
                "hint": "Неполная коробка не считается — нужно деление нацело.",
                "explanation": "n // 6 отбрасывает остаток, то есть неполную коробку.",
            },
        ],
    },
    "Генераторы списков": {
        "title": "Генераторы списков",
        "theory": (
            "Цикл, который собирает новый список, сворачивается в одну строку:\n"
            "`[x * 2 for x in nums]` — каждый элемент, умноженный на 2;\n"
            "`[x for x in nums if x > 0]` — только положительные.\n\n"
            "Читается слева направо: что положить, откуда брать, при каком условии."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": "print([x * x for x in range(4)])",
                "answer": "[0, 1, 4, 9]",
                "hint": "range(4) — это 0, 1, 2, 3. Каждое число возводится в квадрат.",
                "explanation": "Квадраты чисел 0..3 собираются в список.",
            },
            {
                "type": "quiz",
                "prompt": "Что получится?",
                "code": '[c for c in "abc" if c != "b"]',
                "options": ["['a', 'c']", "['b']", "'ac'", "['a', 'b', 'c']"],
                "answer": "['a', 'c']",
                "hint": "Условие отбрасывает одну букву, результат — список.",
                "explanation": 'Остаются символы, не равные "b", и складываются в список.',
            },
            {
                "type": "code",
                "prompt": "Верни список квадратов только чётных чисел — одним генератором списка.",
                "starter_code": "def solve(numbers):\n    return []",
                "reference_solution": (
                    "def solve(numbers):\n    return [n * n for n in numbers if n % 2 == 0]"
                ),
                "tests": [
                    {"call": "solve([1, 2, 3, 4])", "expect": [4, 16]},
                    {"call": "solve([])", "expect": []},
                    {"call": "solve([5, 7])", "expect": []},
                ],
                "hint": "[что for n in numbers if условие]",
                "explanation": "Условие отбирает чётные, выражение слева возводит их в квадрат.",
            },
        ],
    },
    "Модель объектов": {
        "title": "Модель объектов",
        "theory": (
            "Переменная в Python — не коробка, а **ярлык** на объект. "
            "`b = a` не копирует список, а вешает второй ярлык на тот же объект.\n\n"
            "`==` сравнивает значения, `is` — проверяет, один ли это объект.\n"
            "`[1] == [1]` — True, а `[1] is [1]` — False: списки равны, но их два."
        ),
        "tasks": [
            {
                "type": "predict",
                "prompt": "Что выведет код?",
                "code": "a = [1, 2]\nb = a\nb.append(3)\nprint(a)",
                "answer": "[1, 2, 3]",
                "hint": "Сколько списков существует в этой программе?",
                "explanation": "a и b — ярлыки одного списка, изменение видно через оба.",
            },
            {
                "type": "quiz",
                "prompt": "Что выведет код?",
                "code": "print([1] == [1], [1] is [1])",
                "options": ["True False", "True True", "False False", "False True"],
                "answer": "True False",
                "hint": "Значения равны, а объектов создано два.",
                "explanation": "== сравнивает содержимое, is — идентичность объектов.",
            },
            {
                "type": "code",
                "prompt": (
                    "Верни True, если a и b — один и тот же объект, а не просто равные значения."
                ),
                "starter_code": "def solve(a, b):\n    return False",
                "reference_solution": "def solve(a, b):\n    return a is b",
                "tests": [
                    {"call": "solve([1], [1])", "expect": False},
                    {"call": "solve(None, None)", "expect": True},
                    {"call": "(lambda x: solve(x, x))([1, 2])", "expect": True},
                ],
                "hint": "Для проверки идентичности есть отдельный оператор.",
                "explanation": "a is b истинно, только когда это один объект.",
            },
        ],
    },
}
