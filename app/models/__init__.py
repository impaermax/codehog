"""All models in one place, so the metadata knows about every table."""

from app.models.admin import BonusGrant
from app.models.base import Base, TimestampMixin, utc_now
from app.models.game import Item, Slot, UserItem, WheelSpin
from app.models.learning import Course, Lesson, Module, Submission, Task, TaskKind, TestAttempt
from app.models.reward import Achievement, ConditionType, Meme, UserAchievement
from app.models.user import CoinReason, CoinTransaction, DailyActivity, Level, User

__all__ = [
    "Base",
    "TimestampMixin",
    "utc_now",
    "User",
    "DailyActivity",
    "CoinTransaction",
    "Level",
    "CoinReason",
    "TestAttempt",
    "Course",
    "Module",
    "Lesson",
    "Task",
    "Submission",
    "TaskKind",
    "Item",
    "UserItem",
    "WheelSpin",
    "Slot",
    "BonusGrant",
    "Achievement",
    "UserAchievement",
    "Meme",
    "ConditionType",
]
