"""Coins, streaks and the wheel. Every coin movement goes through this module."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CoinReason,
    CoinTransaction,
    Course,
    DailyActivity,
    Item,
    User,
    UserItem,
    WheelSpin,
)

# Rewards are tuned so that the first skin can be bought on day one.
COINS_PER_LESSON = 10
REWARDED_LESSONS_PER_DAY = 3
COINS_PER_DAY = 15
COINS_PER_STREAK_WEEK = 35
LESSONS_PER_SPIN = 5
# Skin tiers in the shop: tier 1 is open right away, the rest unlock one per module.
MAX_SKIN_TIER = 6

# (coins, weight). The average prize is 24 coins.
SECTORS: list[tuple[int, int]] = [(10, 45), (20, 30), (40, 18), (80, 6), (150, 1)]
TOTAL_WEIGHT = sum(weight for _, weight in SECTORS)


@dataclass
class LessonOutcome:
    """What the learner got for a lesson, shown in the UI."""

    coins: int = 0
    xp: int = 0
    daily_bonus: int = 0
    streak_bonus: int = 0
    streak: int = 0
    spins_available: int = 0
    reward_capped: bool = False

    @property
    def total_coins(self) -> int:
        return self.coins + self.daily_bonus + self.streak_bonus


class EconomyError(Exception):
    """The action is not allowed: not enough coins, no spins, or a locked tier.

    The message is shown to the learner as is.
    """


class Economy:
    """The single place where coins are earned and spent."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- internals ---

    def _apply(self, user: User, amount: int, reason: CoinReason, comment: str = "") -> None:
        """Change the balance and record it in the ledger. The balance never goes negative."""
        if user.is_admin and amount < 0:
            # Admin purchases are free: the admin tests the shop rather than plays.
            self.session.add(
                CoinTransaction(
                    user_id=user.id,
                    amount=0,
                    reason=reason,
                    comment=f"{comment} (админ, без списания)"[:255],
                    balance_after=user.coins,
                )
            )
            return
        new_balance = user.coins + amount
        if new_balance < 0:
            raise EconomyError("Недостаточно монет")
        user.coins = new_balance
        self.session.add(
            CoinTransaction(
                user_id=user.id,
                amount=amount,
                reason=reason,
                comment=comment,
                balance_after=new_balance,
            )
        )

    def _day(self, user: User, day: date) -> DailyActivity:
        activity = self.session.scalar(
            select(DailyActivity).where(DailyActivity.user_id == user.id, DailyActivity.day == day)
        )
        if activity is None:
            activity = DailyActivity(user_id=user.id, day=day)
            self.session.add(activity)
            self.session.flush()
        return activity

    # --- lessons and streaks ---

    def complete_lesson(self, user: User, xp: int, today: date | None = None) -> LessonOutcome:
        """Credit a completed lesson: XP, coins, streak and the right to spin the wheel."""
        today = today or date.today()
        outcome = LessonOutcome(xp=xp)
        activity = self._day(user, today)

        # The streak is counted once per day.
        if user.last_active_on != today:
            yesterday = today - timedelta(days=1)
            user.streak_current = (
                user.streak_current + 1 if user.last_active_on == yesterday else 1
            )
            user.streak_best = max(user.streak_best, user.streak_current)
            user.last_active_on = today

        user.xp += xp
        activity.xp_earned += xp
        activity.lessons_done += 1
        outcome.streak = user.streak_current

        # Coins are paid only for the first three new lessons of the day.
        if activity.lessons_done <= REWARDED_LESSONS_PER_DAY:
            outcome.coins = COINS_PER_LESSON
            self._apply(user, COINS_PER_LESSON, CoinReason.LESSON, "урок пройден")
            user.lessons_since_wheel += 1
        else:
            outcome.reward_capped = True

        # A bonus for studying today at all.
        if not activity.streak_reward_given and outcome.coins:
            outcome.daily_bonus = COINS_PER_DAY
            self._apply(user, COINS_PER_DAY, CoinReason.STREAK, f"день {user.streak_current}")
            activity.streak_reward_given = True
            # Every full week of the streak gets its own reward.
            if user.streak_current % 7 == 0:
                outcome.streak_bonus = COINS_PER_STREAK_WEEK
                self._apply(
                    user,
                    COINS_PER_STREAK_WEEK,
                    CoinReason.STREAK,
                    f"{user.streak_current} дней подряд",
                )

        activity.coins_earned += outcome.total_coins
        outcome.spins_available = self.available_spins(user)
        self.session.commit()
        return outcome

    def check_streak(self, user: User, today: date | None = None) -> None:
        """Reset the streak if a day was skipped between sessions."""
        today = today or date.today()
        if user.last_active_on and (today - user.last_active_on).days > 1:
            user.streak_current = 0
            self.session.commit()

    # --- wheel ---

    def available_spins(self, user: User) -> int:
        """Every fifth rewarded lesson gives one spin."""
        earned = user.lessons_since_wheel // LESSONS_PER_SPIN
        used = self.session.query(WheelSpin).filter(WheelSpin.user_id == user.id).count()
        return max(0, earned - used)

    def spin(self, user: User) -> WheelSpin:
        """One wheel spin. The server picks the prize; a repeated request adds nothing."""
        if self.available_spins(user) <= 0 and not user.is_admin:
            raise EconomyError("Вращений пока нет — пройдите ещё уроки")

        milestone = self.session.query(WheelSpin).filter(WheelSpin.user_id == user.id).count() + 1
        roll = secrets.randbelow(TOTAL_WEIGHT)
        cumulative = 0
        sector, prize = 0, SECTORS[0][0]
        for index, (coins, weight) in enumerate(SECTORS):
            cumulative += weight
            if roll < cumulative:
                sector, prize = index, coins
                break

        wheel_spin = WheelSpin(
            user_id=user.id, milestone=milestone, sector_index=sector, coins_won=prize
        )
        self.session.add(wheel_spin)
        self._apply(user, prize, CoinReason.WHEEL, f"колесо, веха {milestone}")
        try:
            self.session.commit()
        except IntegrityError:  # a parallel request has already paid this milestone
            self.session.rollback()
            existing = self.session.scalar(
                select(WheelSpin).where(
                    WheelSpin.user_id == user.id, WheelSpin.milestone == milestone
                )
            )
            if existing:
                return existing
            raise
        return wheel_spin

    # --- shop ---

    def unlocked_tier(self, user: User) -> int:
        """Highest skin tier open in the shop: 1 at first, plus one per completed module.

        A module counts as completed when all its lessons are. Once the whole
        course is completed, every tier opens, even if it had fewer than five modules.
        """
        if user.is_admin:
            return MAX_SKIN_TIER
        course = self.session.scalar(
            select(Course)
            .where(Course.user_id == user.id, Course.is_active.is_(True))
            .order_by(Course.id.desc())
        )
        if course is None:
            return 1
        completed = sum(
            1
            for module in course.modules
            if module.lessons and all(lesson.is_completed for lesson in module.lessons)
        )
        if course.modules and completed == len(course.modules):
            return MAX_SKIN_TIER
        return min(MAX_SKIN_TIER, 1 + completed)

    def has_skin(self, user: User) -> bool:
        return any(owned.item.tier >= 1 for owned in user.items)

    def price(self, user: User, item: Item) -> int:
        """The first tier-1 skin is free: it is the starter hedgehog."""
        if item.tier == 1 and not self.has_skin(user):
            return 0
        return item.price

    def buy(self, user: User, item: Item) -> UserItem:
        """Buy a skin: charge coins, add it to the collection and make it active."""
        owned = self.session.scalar(
            select(UserItem).where(UserItem.user_id == user.id, UserItem.item_id == item.id)
        )
        if owned:
            return owned
        if item.tier > self.unlocked_tier(user):
            raise EconomyError(f"Этот уровень откроется, когда пройдёшь модуль {item.tier - 1}")
        price = self.price(user, item)
        if not user.is_admin and user.coins < price:
            raise EconomyError(f"Не хватает {price - user.coins} монет")

        self._apply(
            user,
            -price,
            CoinReason.PURCHASE,
            item.name + (" (стартовый ёж)" if price == 0 else ""),
        )
        purchase = UserItem(user_id=user.id, item_id=item.id, is_equipped=False)
        self.session.add(purchase)
        self.session.flush()
        self.equip(user, purchase)
        self.session.commit()
        return purchase

    def equip(self, user: User, owned: UserItem) -> None:
        """Make a hedgehog active. A user always has exactly one active hedgehog.

        The previous one is switched off in the database first, then the new
        one is switched on. In the opposite order the unique index
        uq_inventory_one_active would briefly see two active rows and reject
        the update.
        """
        # Look the previous one up with a query rather than through user.items:
        # that list is loaded once and does not see skins bought in this session.
        self.session.flush()
        previous = self.session.scalars(
            select(UserItem).where(
                UserItem.user_id == user.id,
                UserItem.is_equipped.is_(True),
                UserItem.id != owned.id,
            )
        ).all()
        for other in previous:
            other.is_equipped = False
        self.session.flush()
        owned.is_equipped = True
