"""Interface translations. Russian by default, plus English and Chechen.

Only a few keys are translated on purpose: the landing page, the header and
the buttons, which is what a visitor sees before signing up. Anything missing
from a dictionary is shown in Russian, so adding a language breaks nothing.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "ru"

LANGUAGES = {
    "ru": "РУС",
    "en": "ENG",
    "ce": "НОХЧ",  # an easter egg: the Chechen language
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "hero.title1": "Освой Python.",
        "hero.title2": "Собери",
        "hero.accent": "всех ежей",
        "hero.subtitle": "Шесть заданий определят твой уровень. Дальше — короткие уроки "
        "ровно под тебя, монеты за практику и 54 ежа в коллекции.",
        "hero.button": "Пройти тест →",
        "hero.note": "Без регистрации · 5–8 минут · можно с нуля",
        "step.test": "Тест на уровень",
        "step.course": "Личный курс",
        "step.practice": "Практика и награды",
        "card.course.title": "Курс под твой уровень",
        "card.course.text": "Не общий поток для всех. После теста маршрут собирается "
        "по твоим пробелам — от переменных до декораторов.",
        "card.code.title": "Код проверяется по-настоящему",
        "card.code.text": "Пишешь функцию — она запускается и прогоняется тестами. Видно, "
        "что вернулось и где именно разошлось с ожидаемым.",
        "card.coins.title": "Монеты и ёж",
        "card.coins.text": "За уроки и серии дней падают монеты. На них покупаются скины ежа, "
        "а каждый пройденный модуль открывает новый уровень коллекции.",
        "header.login": "Войти",
        "header.logout": "Выйти",
        "header.profile": "Профиль",
        "header.shop": "Магазин",
        "header.admin": "Панель",
    },
    "en": {
        "hero.title1": "Learn Python.",
        "hero.title2": "Collect",
        "hero.accent": "every hedgehog",
        "hero.subtitle": "Six questions find your level. Then short lessons built for you, "
        "coins for practice, and 54 hedgehogs to collect.",
        "hero.button": "Take the test →",
        "hero.note": "No sign-up · 5–8 minutes · beginners welcome",
        "step.test": "Placement test",
        "step.course": "Personal course",
        "step.practice": "Practice and rewards",
        "card.course.title": "A course for your level",
        "card.course.text": "Not one stream for everyone. After the test the path is built "
        "around your gaps — from variables to decorators.",
        "card.code.title": "Your code actually runs",
        "card.code.text": "Write a function and it is executed against real tests. You see what "
        "it returned and exactly where it differs from the expected value.",
        "card.coins.title": "Coins and the hedgehog",
        "card.coins.text": "Lessons and daily streaks drop coins. Spend them on hedgehog skins — "
        "every finished module unlocks a new tier of the collection.",
        "header.login": "Sign in",
        "header.logout": "Sign out",
        "header.profile": "Profile",
        "header.shop": "Shop",
        "header.admin": "Admin",
    },
    "ce": {
        "hero.title1": "Python Iамае.",
        "hero.title2": "Кечбе хьайн",
        "hero.accent": "кибер-зу",
        "hero.subtitle": "Ялх хаттаро хьан тIегIа гойту. ТIаккха — хьуна тIехь жима дешарш, "
        "болх барна ахча, а хьайн куьйгашца кечйина зу.",
        "hero.button": "Тест яха →",
        "hero.note": "Регистраци йоцуш · 5–8 минот · дуьххьара а мега",
        "step.test": "ТIегIан тест",
        "step.course": "Шен курс",
        "step.practice": "Практика а, совгIаташ а",
        "card.course.title": "Хьан тIегIане курс",
        "card.course.text": "Массарна цхьаъ доцуш. Тест яьккхича, некъ хьан меттигех схьаоьцу — "
        "переменнойх дуьйна декораторашка кхаччалц.",
        "card.code.title": "Код бакъдолуш толлу",
        "card.code.text": "Ахьа функци язъеча, иза чекхйолу а, тесташца толлу а. Гуш ду цо "
        "хIун жоп делла а, мичахь хийцалуш ду а.",
        "card.coins.title": "Ахча а, зу а",
        "header.login": "ЧуьраваллаI",
        "header.logout": "Аравала",
        "header.shop": "Туька",
        "header.admin": "Панель",
    },
}


def get_translations(lang: str) -> dict[str, str]:
    """The language's dictionary on top of Russian: untranslated keys stay Russian."""
    result = dict(TRANSLATIONS[DEFAULT_LANGUAGE])
    result.update(TRANSLATIONS.get(lang, {}))
    return result


def pick_language(value: str | None) -> str:
    """A supported language code, or the default one."""
    return value if value in LANGUAGES else DEFAULT_LANGUAGE
