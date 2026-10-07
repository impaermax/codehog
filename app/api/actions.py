"""JSON endpoints: answer checks, hints, the wheel and the shop.

Request and response bodies are Pydantic schemas from schemas.py: FastAPI
validates the input (422 on error), drops undeclared fields from responses
and shows everything in the docs at /hog/docs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import GuestToken, RequiredUser, SessionDep
from app.config import settings
from app.models import Item, Level, Submission, Task, TaskKind, TestAttempt, User, UserItem
from app.services.ai import AIClient, AIUnavailableError
from app.services.awards import MedalService, random_meme
from app.services.economy import SECTORS, Economy, EconomyError
from app.services.sandbox import Sandbox
from app.services.testbank import BY_ID, AdaptiveTest

HINT_PROMPT = (
    "You are a Python mentor. Answer in Russian, in two or three sentences. "
    "Point the learner in the right direction, but never give the full solution code."
)

# /api on maks.my is already taken by another platform, hence /hog.
# Every refusal is returned as {"detail": "..."}, which the docs show.
router = APIRouter(
    prefix="/hog",
    responses={
        400: {"model": schemas.ErrorOut},
        401: {"model": schemas.ErrorOut},
        404: {"model": schemas.ErrorOut},
    },
)


def _public_url(path: str) -> str:
    """Turn a path stored in the database into a URL for the browser.

    Links are stored relative to the app (/static/...), so they do not depend
    on the sub-path it is deployed under. BASE_PATH is added here, on output.
    External URLs are returned as is.
    """
    if path.startswith(("http://", "https://")) or not path.startswith("/"):
        return path
    return f"{settings.base_path}{path}"


def _own_task(session: Session, task_id: int, user: User) -> Task:
    """The task, if it belongs to the user's course; otherwise 404."""
    task = session.get(Task, task_id)
    if task is None or task.lesson.module.course.user_id != user.id:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    return task


# --- placement test ---


@router.post(
    "/test/submit", tags=["test"], response_model=schemas.TestNextStage | schemas.TestResult
)
def submit_test(
    request: Request,
    body: schemas.TestSubmit,
    session: SessionDep,
    guest: GuestToken,
):
    """Accept the answers of a stage; return the next stage or the result.

    experience is the answer given before the test: none, other or python.
    Those who have never programmed skip the test: they get the beginner
    level right away and their course starts with the intro module.
    """
    session_token = guest or request.client.host
    if body.experience == "none":
        session.add(
            TestAttempt(
                session_token=session_token,
                correct_count=0,
                total_count=0,
                determined_level=Level.BEGINNER,
                experience=body.experience,
            )
        )
        session.commit()
        return {
            "done": True,
            "from_zero": True,
            "level": Level.BEGINNER.value,
            "level_label": Level.BEGINNER.label,
            "correct": 0,
            "total": 0,
            "weak_topics": [],
            "explanations": [],
        }

    graded = [
        {
            "id": question.id,
            "given": given.answer,
            "correct": given.answer == question.answer,
            "topic": question.topic,
        }
        for given in body.answers
        if (question := BY_ID.get(given.id)) is not None
    ]

    next_questions = AdaptiveTest.next_stage(graded)
    if next_questions:
        return {
            "done": False,
            "questions": [question.to_client() for question in next_questions],
            "progress": len(graded),
        }

    level = AdaptiveTest.determine_level(graded)
    attempt = TestAttempt(
        session_token=session_token,
        correct_count=sum(1 for answer in graded if answer["correct"]),
        total_count=len(graded),
        determined_level=level,
        experience=body.experience,
    )
    attempt.answers = graded
    session.add(attempt)
    session.commit()

    return {
        "done": True,
        "from_zero": False,
        "level": level.value,
        "level_label": level.label,
        "correct": attempt.correct_count,
        "total": attempt.total_count,
        "weak_topics": AdaptiveTest.weak_topics(graded),
        "explanations": [
            {
                "id": answer["id"],
                "correct": answer["correct"],
                "text": BY_ID[answer["id"]].explanation,
            }
            for answer in graded
        ],
    }


# --- tasks ---


@router.post("/task/{task_id}/check", tags=["lessons"], response_model=schemas.TaskResult)
def check_task(
    task_id: int,
    body: schemas.TaskAnswer,
    user: RequiredUser,
    session: SessionDep,
):
    """Check an answer. Code is run in the sandbox, other answers are compared with the key."""
    task = _own_task(session, task_id, user)
    is_correct, output, error, details = False, "", "", []

    if task.kind == TaskKind.CODE:
        result = Sandbox().run(body.code, task.checks)
        is_correct, output, error = result.passed, result.stdout, result.error
        details = [
            {
                "call": check.call,
                "expected": check.expected,
                "got": check.got,
                "passed": check.passed,
                "error": check.error,
            }
            for check in result.checks
        ]
        session.add(
            Submission(
                user_id=user.id,
                task_id=task.id,
                code=body.code,
                passed=is_correct,
                output=output[:2000],
                error=error[:2000],
                duration_ms=result.duration_ms,
            )
        )
    else:
        # Whitespace is not a mistake: "[1,2,3]" and "[1, 2, 3]" are the same answer.
        expected = "".join((task.answer or "").split())
        is_correct = "".join(body.answer.split()) == expected
        session.add(
            Submission(user_id=user.id, task_id=task.id, code=body.answer, passed=is_correct)
        )

    if is_correct and not task.is_completed:
        task.is_completed = True

    lesson = task.lesson
    lesson_result = None
    if is_correct and all(t.is_completed for t in lesson.tasks) and not lesson.is_completed:
        lesson.is_completed = True
        session.flush()
        outcome = Economy(session).complete_lesson(user, lesson.xp_reward)
        # Medals are checked after the reward, so conditions see fresh data.
        new_medals = MedalService(session).check(user)
        meme = random_meme(session)
        lesson_result = {
            "coins": outcome.total_coins,
            "xp": outcome.xp,
            "streak": outcome.streak,
            "spins": outcome.spins_available,
            "capped": outcome.reward_capped,
            "medals": [
                {"icon": medal.icon, "title": medal.title, "description": medal.description}
                for medal in new_medals
            ],
            "meme": {"url": _public_url(meme.image_url), "caption": meme.caption}
            if meme
            else None,
        }
    session.commit()

    return {
        "correct": is_correct,
        "output": output,
        "error": error,
        "checks": details,
        "explanation": task.solution if is_correct else "",
        "hint": task.hint,
        "lesson_done": lesson_result,
    }


@router.post("/task/{task_id}/hint", tags=["lessons"], response_model=schemas.HintOut)
def get_hint(
    task_id: int,
    body: schemas.HintRequest,
    user: RequiredUser,
    session: SessionDep,
):
    """A live hint from the model based on the learner's code.

    Without an API key the task's own static hint is returned.
    """
    task = _own_task(session, task_id, user)
    client = AIClient()
    if not client.available:
        return {
            "hint": task.hint or "Перечитайте условие и разберите пример из теории.",
            "source": "static",
        }

    code = body.code[:2000]
    try:
        reply = client.ask(
            HINT_PROMPT,
            f"Task: {task.prompt}\n\nLearner's code:\n{code or '(empty)'}\n\n"
            "Say what is wrong or what to do next.",
            max_tokens=250,
            temperature=0.5,
        )
        return {"hint": reply.text.strip(), "source": reply.model}
    except AIUnavailableError:
        return {"hint": task.hint or "Разберите пример из теории ещё раз.", "source": "static"}


# --- wheel ---


@router.get("/wheel/state", tags=["wheel"], response_model=schemas.WheelState)
def wheel_state(user: RequiredUser, session: SessionDep):
    return {
        "spins": Economy(session).available_spins(user),
        "coins": user.coins,
        "sectors": [{"coins": coins, "weight": weight} for coins, weight in SECTORS],
    }


@router.post("/wheel/spin", tags=["wheel"], response_model=schemas.WheelSpin)
def spin_wheel(user: RequiredUser, session: SessionDep):
    economy = Economy(session)
    try:
        wheel_spin = economy.spin(user)
    except EconomyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "sector": wheel_spin.sector_index,
        "coins_won": wheel_spin.coins_won,
        "coins": user.coins,
        "spins_left": economy.available_spins(user),
    }


# --- shop ---


@router.post(
    "/shop/buy/{sku}", tags=["shop"], response_model=schemas.PurchaseOut, summary="Buy a skin"
)
def buy_skin(sku: str, user: RequiredUser, session: SessionDep):
    """The skin is added to the collection and becomes active right away.

    400: not enough coins, or the collection tier is still locked.
    """
    item = session.scalar(select(Item).where(Item.sku == sku, Item.is_active.is_(True)))
    if item is None:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    try:
        purchase = Economy(session).buy(user, item)
    except EconomyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "ok": True,
        "coins": user.coins,
        "equipped": purchase.is_equipped,
        "slot": item.slot.value,
        "asset": item.asset_key,
    }


@router.post(
    "/shop/equip/{sku}",
    tags=["shop"],
    response_model=schemas.EquipOut,
    summary="Make a hedgehog active",
)
def equip_skin(sku: str, user: RequiredUser, session: SessionDep):
    """A skin from the collection becomes active; the previous one stops being active.

    404: the skin is not in the user's collection.
    """
    item = session.scalar(select(Item).where(Item.sku == sku))
    owned = (
        session.scalar(
            select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item.id)
        )
        if item
        else None
    )
    if owned is None:
        raise HTTPException(status_code=404, detail="Этого предмета у вас нет")
    # There is always exactly one active hedgehog: it cannot be taken off.
    # A repeated request for the active one changes nothing.
    Economy(session).equip(user, owned)
    session.commit()
    return {
        "ok": True,
        "equipped": owned.is_equipped,
        "slot": item.slot.value,
        "asset": item.asset_key,
    }
