"""Background lesson preparation.

Generating a lesson with the model takes 15–25 seconds, which is too long
to keep a learner waiting. So:
  * the first lesson is filled instantly from a ready-made lesson;
  * the next ones are prepared in the background while the current one is studied.
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Course, TestAttempt, User

logger = logging.getLogger("codehog.prefetch")

BUFFER = 3  # how many lessons to keep ready ahead
_busy: set[int] = set()
_lock = threading.Lock()


def _prepare(user_id: int, count: int) -> None:
    from app.services.course import CourseGenerator
    from app.services.testbank import AdaptiveTest

    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if user is None:
            return
        course = session.scalar(
            select(Course).where(Course.user_id == user_id).order_by(Course.id.desc())
        )
        if course is None:
            return

        attempt = session.scalar(
            select(TestAttempt)
            .where(TestAttempt.user_id == user_id)
            .order_by(TestAttempt.id.desc())
        )
        weak_topics = AdaptiveTest.weak_topics(attempt.answers) if attempt else []

        generator = CourseGenerator(session)
        done = 0
        for lesson in course.all_lessons:
            if done >= count:
                break
            if lesson.tasks:
                continue
            generator.fill_lesson(lesson, user, weak_topics)
            done += 1
        if done:
            logger.info("prepared %s lessons in the background (user %s)", done, user_id)
    except Exception as e:  # a background job must never take the app down
        logger.warning("background preparation failed: %s", str(e)[:200])
    finally:
        session.close()
        with _lock:
            _busy.discard(user_id)


def prefetch_lessons(user_id: int, count: int = BUFFER) -> bool:
    """Queue preparation in the background. A repeated call for the same user is ignored."""
    with _lock:
        if user_id in _busy:
            return False
        _busy.add(user_id)
    thread = threading.Thread(target=_prepare, args=(user_id, count), daemon=True)
    thread.start()
    return True
