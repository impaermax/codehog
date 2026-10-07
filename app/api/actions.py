"""JSON-эндпоинты: проверка ответов, колесо, магазин, подсказки ИИ.

Тела запросов и ответов описаны Pydantic-схемами в schemas.py: FastAPI сам
проверяет входные данные (422 при ошибке), отрезает лишнее в ответе и
показывает всё это в документации /hog/docs.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as с
from app.api.deps import нужен_пользователь, токен_гостя
from app.config import settings
from app.database import получить_сессию
from app.models import Item, Lesson, Submission, Task, TestAttempt, User, UserItem, ТипЗадания, Уровень
from app.services.ai import ИИНедоступен, КлиентИИ
from app.services.awards import Медали, случайный_мем
from app.services.economy import НедостаточноМонет, СЕКТОРА, Экономика
from app.services.sandbox import Песочница
from app.services.testbank import АдаптивныйТест, ПО_ID

# Префикс /api на maks.my уже занят другой платформой, поэтому свой — /hog.
# Любой отказ отдаётся как {"detail": "..."} — это видно в документации.
роутер = APIRouter(
    prefix="/hog",
    responses={400: {"model": с.ErrorOut}, 401: {"model": с.ErrorOut}, 404: {"model": с.ErrorOut}},
)


# --- входной тест ---

@роутер.post("/test/submit", tags=["тест"],
             response_model=с.TestNextStage | с.TestResult)
def проверить_тест(
    request: Request,
    данные: с.TestSubmit,
    сессия: Session = Depends(получить_сессию),
    гость: str = Depends(токен_гостя),
):
    """Принимает ответы этапа, отдаёт следующий этап или итог.

    Поле experience — ответ на вопрос перед тестом: none, other или python.
    Кто никогда не программировал, тест не проходит: сразу получает уровень
    «новичок», а курс ему собирается с нулевого модуля.
    """
    опыт = данные.experience
    if опыт == "none":
        попытка = TestAttempt(
            session_token=гость or request.client.host,
            correct_count=0, total_count=0,
            determined_level=Уровень.НОВИЧОК, experience=опыт,
        )
        сессия.add(попытка)
        сессия.commit()
        return {
            "done": True, "from_zero": True,
            "level": Уровень.НОВИЧОК.value, "level_label": Уровень.НОВИЧОК.подпись,
            "correct": 0, "total": 0, "weak_topics": [], "explanations": [],
        }

    разобранные = []
    for о in данные.answers:
        вопрос = ПО_ID.get(о.id)
        if вопрос is None:
            continue
        разобранные.append({
            "id": вопрос.id,
            "given": о.answer,
            "correct": о.answer == вопрос.ответ,
            "topic": вопрос.тема,
        })

    следующие = АдаптивныйТест.следующий_этап(разобранные)
    if следующие:
        return {
            "done": False,
            "questions": [в.для_клиента() for в in следующие],
            "progress": len(разобранные),
        }

    уровень = АдаптивныйТест.определить_уровень(разобранные)
    слабые = АдаптивныйТест.слабые_темы(разобранные)
    попытка = TestAttempt(
        session_token=гость or request.client.host,
        correct_count=sum(1 for о in разобранные if о["correct"]),
        total_count=len(разобранные),
        determined_level=уровень,
        experience=опыт,
    )
    попытка.ответы = разобранные
    сессия.add(попытка)
    сессия.commit()

    return {
        "done": True,
        "from_zero": False,
        "level": уровень.value,
        "level_label": уровень.подпись,
        "correct": попытка.correct_count,
        "total": попытка.total_count,
        "weak_topics": слабые,
        "explanations": [
            {"id": о["id"], "correct": о["correct"], "text": ПО_ID[о["id"]].объяснение}
            for о in разобранные if о["id"] in ПО_ID
        ],
    }


def _адрес(путь: str) -> str:
    """Путь из базы -> адрес для браузера.

    В базе ссылки хранятся относительно приложения (/static/...), чтобы не
    зависеть от того, в каком подкаталоге оно развёрнуто. Префикс BASE_PATH
    добавляется здесь, при отдаче. Внешние адреса возвращаются как есть.
    """
    if путь.startswith(("http://", "https://")) or not путь.startswith("/"):
        return путь
    return f"{settings.base_path}{путь}"


# --- проверка заданий ---

@роутер.post("/task/{task_id}/check", tags=["уроки"], response_model=с.TaskResult)
def проверить_задание(
    task_id: int,
    данные: с.TaskAnswer,
    юзер: User = Depends(нужен_пользователь),
    сессия: Session = Depends(получить_сессию),
):
    задание = сессия.get(Task, task_id)
    if задание is None or задание.lesson.module.course.user_id != юзер.id:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    ответ_ученика = данные.answer
    код = данные.code
    верно, вывод, ошибка, детали = False, "", "", []

    if задание.kind == ТипЗадания.КОД:
        результат = Песочница().запустить(код, задание.проверки)
        верно, вывод, ошибка = результат.passed, результат.stdout, результат.error
        детали = [
            {"call": п.call, "expected": п.expected, "got": п.got,
             "passed": п.passed, "error": п.error}
            for п in результат.checks
        ]
        сессия.add(Submission(
            user_id=юзер.id, task_id=задание.id, code=код, passed=верно,
            output=вывод[:2000], error=ошибка[:2000], duration_ms=результат.duration_ms,
        ))
    else:
        # пробелы не считаем ошибкой: «[1,2,3]» и «[1, 2, 3]» — один и тот же ответ
        эталон = "".join((задание.answer or "").split())
        верно = "".join(ответ_ученика.split()) == эталон
        сессия.add(Submission(
            user_id=юзер.id, task_id=задание.id, code=ответ_ученика, passed=верно,
        ))

    if верно and not задание.is_completed:
        задание.is_completed = True

    урок = задание.lesson
    итог_урока = None
    if верно and all(з.is_completed for з in урок.tasks) and not урок.is_completed:
        урок.is_completed = True
        сессия.flush()
        итог = Экономика(сессия).отметить_урок(юзер, урок.xp_reward)
        # медали проверяем после начисления: условия считаются по свежим данным
        новые_медали = Медали(сессия).проверить(юзер)
        мем = случайный_мем(сессия)
        итог_урока = {
            "coins": итог.всего_монет,
            "xp": итог.опыт,
            "streak": итог.стрик,
            "spins": итог.вращений_доступно,
            "capped": итог.награда_ограничена,
            "medals": [
                {"icon": м.icon, "title": м.title, "description": м.description}
                for м in новые_медали
            ],
            "meme": {"url": _адрес(мем.image_url), "caption": мем.caption} if мем else None,
        }
    сессия.commit()

    return {
        "correct": верно,
        "output": вывод,
        "error": ошибка,
        "checks": детали,
        "explanation": задание.solution if верно else "",
        "hint": задание.hint,
        "lesson_done": итог_урока,
    }


@роутер.post("/task/{task_id}/hint", tags=["уроки"], response_model=с.HintOut)
def подсказка(
    task_id: int,
    данные: с.HintRequest,
    юзер: User = Depends(нужен_пользователь),
    сессия: Session = Depends(получить_сессию),
):
    """Живая подсказка от модели по коду ученика. Без ключа — статичная из задания."""
    задание = сессия.get(Task, task_id)
    if задание is None or задание.lesson.module.course.user_id != юзер.id:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    клиент = КлиентИИ()
    if not клиент.доступен:
        return {"hint": задание.hint or "Перечитайте условие и разберите пример из теории.",
                "source": "static"}

    код = данные.code[:2000]
    try:
        ответ = клиент.спросить(
            "Ты наставник по Python. Отвечай двумя-тремя предложениями по-русски. "
            "Подсказывай направление, но никогда не давай готовый код целиком.",
            f"Задание: {задание.prompt}\n\nКод ученика:\n{код or '(пусто)'}\n\n"
            f"Скажи, в чём ошибка или что делать дальше.",
            максимум_токенов=250, температура=0.5,
        )
        return {"hint": ответ.текст.strip(), "source": ответ.модель}
    except ИИНедоступен:
        return {"hint": задание.hint or "Разберите пример из теории ещё раз.", "source": "static"}


# --- колесо ---

@роутер.get("/wheel/state", tags=["колесо"], response_model=с.WheelState)
def состояние_колеса(юзер: User = Depends(нужен_пользователь),
                     сессия: Session = Depends(получить_сессию)):
    return {
        "spins": Экономика(сессия).доступно_вращений(юзер),
        "coins": юзер.coins,
        "sectors": [{"coins": м, "weight": в} for м, в in СЕКТОРА],
    }


@роутер.post("/wheel/spin", tags=["колесо"], response_model=с.WheelSpin)
def крутить_колесо(юзер: User = Depends(нужен_пользователь),
                   сессия: Session = Depends(получить_сессию)):
    экономика = Экономика(сессия)
    try:
        вращение = экономика.крутить(юзер)
    except НедостаточноМонет as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "sector": вращение.sector_index,
        "coins_won": вращение.coins_won,
        "coins": юзер.coins,
        "spins_left": экономика.доступно_вращений(юзер),
    }


# --- магазин ---

@роутер.post("/shop/buy/{sku}", tags=["магазин"], response_model=с.PurchaseOut,
             summary="Купить скин")
def купить(sku: str, юзер: User = Depends(нужен_пользователь),
           сессия: Session = Depends(получить_сессию)):
    """Скин попадает в коллекцию и сразу становится активным.

    400 — не хватает монет или уровень коллекции ещё не открыт.
    """
    предмет = сессия.scalar(select(Item).where(Item.sku == sku, Item.is_active.is_(True)))
    if предмет is None:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    try:
        покупка = Экономика(сессия).купить(юзер, предмет)
    except НедостаточноМонет as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "coins": юзер.coins, "equipped": покупка.is_equipped,
            "slot": предмет.slot.value, "asset": предмет.asset_key}


@роутер.post("/shop/equip/{sku}", tags=["магазин"], response_model=с.EquipOut,
             summary="Сделать ежа активным")
def надеть(sku: str, юзер: User = Depends(нужен_пользователь),
           сессия: Session = Depends(получить_сессию)):
    """Активным становится скин из коллекции, прежний перестаёт быть активным. 404 — скина нет в коллекции."""
    предмет = сессия.scalar(select(Item).where(Item.sku == sku))
    покупка = сессия.scalar(
        select(UserItem).where(UserItem.user_id == юзер.id, UserItem.item_id == предмет.id)
    ) if предмет else None
    if покупка is None:
        raise HTTPException(status_code=404, detail="Этого предмета у вас нет")
    # Активный ёж всегда ровно один: снять его, оставив пустое место, нельзя.
    # Повторный запрос на уже активного ничего не меняет.
    Экономика(сессия).надеть(юзер, покупка)
    сессия.commit()
    return {"ok": True, "equipped": покупка.is_equipped, "slot": предмет.slot.value,
            "asset": предмет.asset_key}
