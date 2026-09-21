"""JSON-эндпоинты: проверка ответов, колесо, магазин, подсказки ИИ."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import текущий_пользователь, токен_гостя
from app.database import получить_сессию
from app.models import Item, Lesson, Submission, Task, TestAttempt, User, UserItem, ТипЗадания
from app.services.ai import ИИНедоступен, КлиентИИ
from app.services.awards import Медали, случайный_мем
from app.services.economy import НедостаточноМонет, СЕКТОРА, Экономика
from app.services.sandbox import Песочница
from app.services.testbank import АдаптивныйТест, ПО_ID

# Префикс /api на maks.my уже занят другой платформой, поэтому свой — /hog.
роутер = APIRouter(prefix="/hog")


def _нужен_вход(юзер: User | None) -> User:
    if юзер is None:
        raise HTTPException(status_code=401, detail="Нужно войти")
    return юзер


# --- входной тест ---

@роутер.post("/test/submit")
def проверить_тест(
    request: Request,
    данные: dict = Body(...),
    сессия: Session = Depends(получить_сессию),
    гость: str = Depends(токен_гостя),
):
    """Принимает ответы этапа, отдаёт следующий этап или итог."""
    ответы_клиента = данные.get("answers", [])
    разобранные = []
    for о in ответы_клиента:
        вопрос = ПО_ID.get(о.get("id", ""))
        if вопрос is None:
            continue
        разобранные.append({
            "id": вопрос.id,
            "given": о.get("answer", ""),
            "correct": о.get("answer", "") == вопрос.ответ,
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
    )
    попытка.ответы = разобранные
    сессия.add(попытка)
    сессия.commit()

    return {
        "done": True,
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


# --- проверка заданий ---

@роутер.post("/task/{task_id}/check")
def проверить_задание(
    task_id: int,
    данные: dict = Body(...),
    юзер: User | None = Depends(текущий_пользователь),
    сессия: Session = Depends(получить_сессию),
):
    юзер = _нужен_вход(юзер)
    задание = сессия.get(Task, task_id)
    if задание is None or задание.lesson.module.course.user_id != юзер.id:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    ответ_ученика = str(данные.get("answer", ""))
    код = str(данные.get("code", ""))
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
        эталон = (задание.answer or "").strip()
        верно = ответ_ученика.strip() == эталон
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
            "meme": {"url": мем.image_url, "caption": мем.caption} if мем else None,
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


@роутер.post("/task/{task_id}/hint")
def подсказка(
    task_id: int,
    данные: dict = Body(default={}),
    юзер: User | None = Depends(текущий_пользователь),
    сессия: Session = Depends(получить_сессию),
):
    """Живая подсказка от модели по коду ученика. Без ключа — статичная из задания."""
    юзер = _нужен_вход(юзер)
    задание = сессия.get(Task, task_id)
    if задание is None or задание.lesson.module.course.user_id != юзер.id:
        raise HTTPException(status_code=404, detail="Задание не найдено")

    клиент = КлиентИИ()
    if not клиент.доступен:
        return {"hint": задание.hint or "Перечитайте условие и разберите пример из теории.",
                "source": "static"}

    код = str(данные.get("code", ""))[:2000]
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

@роутер.get("/wheel/state")
def состояние_колеса(юзер: User | None = Depends(текущий_пользователь),
                     сессия: Session = Depends(получить_сессию)):
    юзер = _нужен_вход(юзер)
    return {
        "spins": Экономика(сессия).доступно_вращений(юзер),
        "coins": юзер.coins,
        "sectors": [{"coins": м, "weight": в} for м, в in СЕКТОРА],
    }


@роутер.post("/wheel/spin")
def крутить_колесо(юзер: User | None = Depends(текущий_пользователь),
                   сессия: Session = Depends(получить_сессию)):
    юзер = _нужен_вход(юзер)
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

@роутер.post("/shop/buy/{sku}")
def купить(sku: str, юзер: User | None = Depends(текущий_пользователь),
           сессия: Session = Depends(получить_сессию)):
    юзер = _нужен_вход(юзер)
    предмет = сессия.scalar(select(Item).where(Item.sku == sku, Item.is_active.is_(True)))
    if предмет is None:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    try:
        покупка = Экономика(сессия).купить(юзер, предмет)
    except НедостаточноМонет as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "coins": юзер.coins, "equipped": покупка.is_equipped,
            "slot": предмет.slot.value, "asset": предмет.asset_key}


@роутер.post("/shop/equip/{sku}")
def надеть(sku: str, юзер: User | None = Depends(текущий_пользователь),
           сессия: Session = Depends(получить_сессию)):
    юзер = _нужен_вход(юзер)
    предмет = сессия.scalar(select(Item).where(Item.sku == sku))
    покупка = сессия.scalar(
        select(UserItem).where(UserItem.user_id == юзер.id, UserItem.item_id == предмет.id)
    ) if предмет else None
    if покупка is None:
        raise HTTPException(status_code=404, detail="Этого предмета у вас нет")
    экономика = Экономика(сессия)
    if покупка.is_equipped:
        экономика.снять(покупка)
    else:
        экономика.надеть(юзер, покупка)
    сессия.commit()
    return {"ok": True, "equipped": покупка.is_equipped, "slot": предмет.slot.value,
            "asset": предмет.asset_key}
