"""Монеты, стрик и колесо. Все начисления проходят только через этот класс."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CoinTransaction,
    DailyActivity,
    Item,
    User,
    UserItem,
    WheelSpin,
    ПричинаМонет,
)

# Награды подобраны так, чтобы первую вещь можно было купить в первый день,
# а транспорт за 1800 — примерно за месяц по три урока в день.
МОНЕТ_ЗА_УРОК = 10
НАГРАЖДАЕМЫХ_УРОКОВ_В_ДЕНЬ = 3
МОНЕТ_ЗА_ДЕНЬ = 15
МОНЕТ_ЗА_НЕДЕЛЮ_СТРИКА = 35
УРОКОВ_НА_ВРАЩЕНИЕ = 5

# (монеты, вес). Средняя награда — 24 монеты.
СЕКТОРА: list[tuple[int, int]] = [(10, 45), (20, 30), (40, 18), (80, 6), (150, 1)]
ВСЕГО_ВЕСА = sum(в for _, в in СЕКТОРА)


@dataclass
class ИтогУрока:
    """Что человек получил за урок — показываем это в интерфейсе."""

    монеты: int = 0
    опыт: int = 0
    бонус_дня: int = 0
    бонус_стрика: int = 0
    стрик: int = 0
    вращений_доступно: int = 0
    награда_ограничена: bool = False

    @property
    def всего_монет(self) -> int:
        return self.монеты + self.бонус_дня + self.бонус_стрика


class НедостаточноМонет(Exception):
    """Покупка невозможна: не хватает баланса."""


class Экономика:
    """Единая точка начисления и списания монет."""

    def __init__(self, сессия: Session) -> None:
        self.сессия = сессия

    # --- внутреннее ---

    def _провести(self, юзер: User, сумма: int, причина: ПричинаМонет, комментарий: str = "") -> None:
        """Меняет баланс и пишет запись в журнал. Баланс не уходит в минус."""
        if юзер.is_admin and сумма < 0:
            # у админа траты бесплатны — он проверяет магазин, а не играет
            self.сессия.add(CoinTransaction(
                user_id=юзер.id, amount=0, reason=причина,
                comment=f"{комментарий} (админ, без списания)"[:255], balance_after=юзер.coins,
            ))
            return
        новый = юзер.coins + сумма
        if новый < 0:
            raise НедостаточноМонет("Недостаточно монет")
        юзер.coins = новый
        self.сессия.add(
            CoinTransaction(
                user_id=юзер.id, amount=сумма, reason=причина,
                comment=комментарий, balance_after=новый,
            )
        )

    def _день(self, юзер: User, когда: date) -> DailyActivity:
        запись = self.сессия.scalar(
            select(DailyActivity).where(DailyActivity.user_id == юзер.id, DailyActivity.day == когда)
        )
        if запись is None:
            запись = DailyActivity(user_id=юзер.id, day=когда)
            self.сессия.add(запись)
            self.сессия.flush()
        return запись

    # --- публичное ---

    def отметить_урок(self, юзер: User, опыт: int, сегодня: date | None = None) -> ИтогУрока:
        """Засчитывает пройденный урок: опыт, монеты, стрик, право на вращение."""
        сегодня = сегодня or date.today()
        итог = ИтогУрока(опыт=опыт)
        день = self._день(юзер, сегодня)

        # стрик считаем один раз за день
        if юзер.last_active_on != сегодня:
            вчера = сегодня - timedelta(days=1)
            юзер.streak_current = юзер.streak_current + 1 if юзер.last_active_on == вчера else 1
            юзер.streak_best = max(юзер.streak_best, юзер.streak_current)
            юзер.last_active_on = сегодня

        юзер.xp += опыт
        день.xp_earned += опыт
        день.lessons_done += 1
        итог.стрик = юзер.streak_current

        # монеты за урок — только за первые три новых урока в день
        if день.lessons_done <= НАГРАЖДАЕМЫХ_УРОКОВ_В_ДЕНЬ:
            итог.монеты = МОНЕТ_ЗА_УРОК
            self._провести(юзер, МОНЕТ_ЗА_УРОК, ПричинаМонет.УРОК, "урок пройден")
            юзер.lessons_since_wheel += 1
        else:
            итог.награда_ограничена = True

        # бонус за сам факт занятий сегодня
        if not день.streak_reward_given and итог.монеты:
            итог.бонус_дня = МОНЕТ_ЗА_ДЕНЬ
            self._провести(юзер, МОНЕТ_ЗА_ДЕНЬ, ПричинаМонет.СТРИК, f"день {юзер.streak_current}")
            день.streak_reward_given = True
            # каждая полная неделя стрика — отдельная награда
            if юзер.streak_current % 7 == 0:
                итог.бонус_стрика = МОНЕТ_ЗА_НЕДЕЛЮ_СТРИКА
                self._провести(
                    юзер, МОНЕТ_ЗА_НЕДЕЛЮ_СТРИКА, ПричинаМонет.СТРИК,
                    f"{юзер.streak_current} дней подряд",
                )

        день.coins_earned += итог.всего_монет
        итог.вращений_доступно = self.доступно_вращений(юзер)
        self.сессия.commit()
        return итог

    def проверить_стрик(self, юзер: User, сегодня: date | None = None) -> None:
        """Сбрасывает стрик, если между занятиями пропущен день."""
        сегодня = сегодня or date.today()
        if юзер.last_active_on and (сегодня - юзер.last_active_on).days > 1:
            юзер.streak_current = 0
            self.сессия.commit()

    def доступно_вращений(self, юзер: User) -> int:
        """Право на вращение даёт каждый пятый награждённый урок."""
        всего = юзер.lessons_since_wheel // УРОКОВ_НА_ВРАЩЕНИЕ
        сделано = self.сессия.query(WheelSpin).filter(WheelSpin.user_id == юзер.id).count()
        return max(0, всего - сделано)

    def крутить(self, юзер: User) -> WheelSpin:
        """Один поворот колеса. Приз выбирает сервер, повтор запроса ничего не добавит."""
        доступно = self.доступно_вращений(юзер)
        if доступно <= 0 and not юзер.is_admin:
            raise НедостаточноМонет("Вращений пока нет — пройдите ещё уроки")

        веха = self.сессия.query(WheelSpin).filter(WheelSpin.user_id == юзер.id).count() + 1
        бросок = secrets.randbelow(ВСЕГО_ВЕСА)
        накоплено = 0
        индекс, монеты = 0, СЕКТОРА[0][0]
        for i, (сумма, вес) in enumerate(СЕКТОРА):
            накоплено += вес
            if бросок < накоплено:
                индекс, монеты = i, сумма
                break

        вращение = WheelSpin(user_id=юзер.id, milestone=веха, sector_index=индекс, coins_won=монеты)
        self.сессия.add(вращение)
        self._провести(юзер, монеты, ПричинаМонет.КОЛЕСО, f"колесо, веха {веха}")
        try:
            self.сессия.commit()
        except IntegrityError:  # параллельный запрос уже выдал приз за эту веху
            self.сессия.rollback()
            существующее = self.сессия.scalar(
                select(WheelSpin).where(WheelSpin.user_id == юзер.id, WheelSpin.milestone == веха)
            )
            if существующее:
                return существующее
            raise
        return вращение

    def купить(self, юзер: User, предмет: Item) -> UserItem:
        """Покупка предмета: списание, запись в инвентарь, автоматическая экипировка."""
        уже = self.сессия.scalar(
            select(UserItem).where(UserItem.user_id == юзер.id, UserItem.item_id == предмет.id)
        )
        if уже:
            return уже
        if not юзер.is_admin and юзер.coins < предмет.price:
            raise НедостаточноМонет(f"Не хватает {предмет.price - юзер.coins} монет")

        self._провести(юзер, -предмет.price, ПричинаМонет.ПОКУПКА, предмет.name)
        покупка = UserItem(user_id=юзер.id, item_id=предмет.id, is_equipped=True)
        self.сессия.add(покупка)
        self.сессия.flush()
        self.надеть(юзер, покупка)
        self.сессия.commit()
        return покупка

    def надеть(self, юзер: User, покупка: UserItem) -> None:
        """В одном слоте одновременно только один предмет."""
        слот = покупка.item.slot
        for другой in юзер.items:
            if другой.item.slot == слот and другой.id != покупка.id:
                другой.is_equipped = False
        покупка.is_equipped = True

    def снять(self, покупка: UserItem) -> None:
        покупка.is_equipped = False
