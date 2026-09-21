"""Все модели в одном месте, чтобы metadata знала о каждой таблице."""
from app.models.admin import BonusGrant
from app.models.base import Base, ВременнЫеМетки, сейчас
from app.models.game import Item, Слот, UserItem, WheelSpin
from app.models.learning import (
    Course,
    Lesson,
    Module,
    Submission,
    Task,
    TestAttempt,
    ТипЗадания,
)
from app.models.user import CoinTransaction, DailyActivity, ПричинаМонет, Уровень, User

__all__ = [
    "Base", "ВременнЫеМетки", "сейчас",
    "User", "DailyActivity", "CoinTransaction", "Уровень", "ПричинаМонет",
    "TestAttempt", "Course", "Module", "Lesson", "Task", "Submission", "ТипЗадания",
    "Item", "UserItem", "WheelSpin", "Слот", "BonusGrant",
]
