"""Admin operations: analytics, bonus grants and progress reset."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BonusGrant,
    CoinReason,
    CoinTransaction,
    Course,
    Lesson,
    Level,
    Module,
    Submission,
    TestAttempt,
    User,
    UserItem,
    WheelSpin,
)
from app.services.auth import Auth


@dataclass
class UserRow:
    """One row of the users table in the admin panel."""

    id: int
    username: str
    email: str
    level: str
    stage: str
    lessons_done: int
    total_lessons: int
    coins: int
    streak: int
    skins: int
    last_active: str


@dataclass
class Analytics:
    """Product summary for the admin panel."""

    total_users: int = 0
    active_today: int = 0
    active_week: int = 0
    tests_taken: int = 0
    registered_after_test: int = 0
    started_course: int = 0
    finished_first_lesson: int = 0
    code_attempts: int = 0
    success_rate: float = 0.0
    coins_issued: int = 0
    coins_spent: int = 0
    spins: int = 0
    by_level: dict = field(default_factory=dict)
    users: list = field(default_factory=list)

    @property
    def registration_rate(self) -> float:
        """Share of test takers who signed up, in percent."""
        return self.registered_after_test * 100 / self.tests_taken if self.tests_taken else 0.0

    @property
    def first_lesson_rate(self) -> float:
        """Share of users who completed at least one lesson, in percent."""
        return self.finished_first_lesson * 100 / self.total_users if self.total_users else 0.0


class AdminService:
    """Everything the administrator does."""

    LOGIN = "maks-admin"

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- account ---

    def create_admin(self, password: str, email: str = "maks-admin@codehog.local") -> User:
        """Create the admin account unless it exists. The password comes from ADMIN_PASSWORD."""
        existing = self.session.scalar(select(User).where(User.username == self.LOGIN))
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                self.session.commit()
            return existing
        admin = User(
            email=email,
            username=self.LOGIN,
            password_hash=Auth.hash_password(password),
            level=Level.ADVANCED,
            is_admin=True,
            coins=1_000_000,
        )
        self.session.add(admin)
        self.session.commit()
        return admin

    # --- analytics ---

    def collect(self) -> Analytics:
        db = self.session
        today = date.today()
        week_ago = today - timedelta(days=7)
        stats = Analytics()

        stats.total_users = db.query(User).count()
        stats.active_today = db.query(User).filter(User.last_active_on == today).count()
        stats.active_week = db.query(User).filter(User.last_active_on >= week_ago).count()
        stats.tests_taken = db.query(TestAttempt).count()
        stats.registered_after_test = (
            db.query(TestAttempt).filter(TestAttempt.user_id.isnot(None)).count()
        )
        stats.started_course = db.query(Course).count()
        stats.finished_first_lesson = (
            db.scalar(
                select(func.count(func.distinct(Course.user_id)))
                .join(Module, Module.course_id == Course.id)
                .join(Lesson, Lesson.module_id == Module.id)
                .where(Lesson.is_completed.is_(True))
            )
            or 0
        )

        attempts = db.query(Submission).count()
        successful = db.query(Submission).filter(Submission.passed.is_(True)).count()
        stats.code_attempts = attempts
        stats.success_rate = successful * 100 / attempts if attempts else 0.0

        stats.coins_issued = (
            db.query(func.coalesce(func.sum(CoinTransaction.amount), 0))
            .filter(CoinTransaction.amount > 0)
            .scalar()
            or 0
        )
        stats.coins_spent = abs(
            db.query(func.coalesce(func.sum(CoinTransaction.amount), 0))
            .filter(CoinTransaction.amount < 0)
            .scalar()
            or 0
        )
        stats.spins = db.query(WheelSpin).count()

        stats.by_level = dict(Counter(user.level.label for user in db.query(User).all()))
        stats.users = self._user_rows()
        return stats

    def _user_rows(self) -> list[UserRow]:
        rows = []
        for user in self.session.query(User).order_by(User.id.desc()).limit(200).all():
            course = self.session.scalar(
                select(Course).where(Course.user_id == user.id).order_by(Course.id.desc())
            )
            lessons = course.all_lessons if course else []
            done = sum(1 for lesson in lessons if lesson.is_completed)
            skins = self.session.query(UserItem).filter(UserItem.user_id == user.id).count()
            rows.append(
                UserRow(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    level=user.level.label,
                    stage=self._stage(course, done, len(lessons)),
                    lessons_done=done,
                    total_lessons=len(lessons),
                    coins=user.coins,
                    streak=user.streak_current,
                    skins=skins,
                    last_active=user.last_active_on.isoformat() if user.last_active_on else "—",
                )
            )
        return rows

    @staticmethod
    def _stage(course: Course | None, done: int, total: int) -> str:
        """Funnel stage shown in the admin panel."""
        if course is None:
            return "нет курса"
        if done == 0:
            return "зарегистрировался"
        if total and done >= total:
            return "курс пройден"
        if done < 3:
            return "первые уроки"
        return "в процессе"

    # --- bonuses ---

    def grant_to_all(self, amount: int, comment: str, author: str = "admin") -> BonusGrant:
        """Record a bonus. Each registered user receives it on their next visit."""
        grant = BonusGrant(amount=amount, comment=comment, created_by=author)
        self.session.add(grant)
        self.session.commit()
        return grant

    def grant_pending(self, user: User) -> list[BonusGrant]:
        """Pay out every bonus the user has not received yet. Called on every page."""
        pending = self.session.scalars(
            select(BonusGrant).where(BonusGrant.id > user.last_bonus_id).order_by(BonusGrant.id)
        ).all()
        if not pending:
            return []
        for grant in pending:
            user.coins += grant.amount
            self.session.add(
                CoinTransaction(
                    user_id=user.id,
                    amount=grant.amount,
                    reason=CoinReason.BONUS,
                    comment=f"бонус: {grant.comment}"[:255],
                    balance_after=user.coins,
                )
            )
            user.last_bonus_id = grant.id
        self.session.commit()
        return list(pending)

    # --- reset ---

    def reset(self, user: User) -> None:
        """Wipe progress: course, coins, collection, streak and attempts."""
        db = self.session
        db.query(Submission).filter(Submission.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(UserItem).filter(UserItem.user_id == user.id).delete(synchronize_session=False)
        db.query(WheelSpin).filter(WheelSpin.user_id == user.id).delete(synchronize_session=False)
        db.query(CoinTransaction).filter(CoinTransaction.user_id == user.id).delete(
            synchronize_session=False
        )
        for course in db.query(Course).filter(Course.user_id == user.id).all():
            db.delete(course)
        user.coins = 1_000_000 if user.is_admin else 0
        user.xp = 0
        user.streak_current = 0
        user.streak_best = 0
        user.last_active_on = None
        user.lessons_since_wheel = 0
        db.commit()
