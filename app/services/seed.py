"""Initial shop catalog: hedgehog skins.

The shop sells skins, ready-made looks of the hedgehog, rather than clothing.
Skins are split into six tiers of nine. Tier 1 is available right away and
the starter hedgehog is picked from it at sign-up. Tiers 2–6 unlock one by
one as the learner completes course modules.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, Slot

# Skin price for each tier. The first tier-1 skin is free.
TIER_PRICES = {1: 40, 2: 100, 3: 200, 4: 350, 5: 550, 6: 800}

# Tier -> nine skins as (name, description), in the order of the design sheets:
# left to right, top to bottom. Image: static/img/skins/{tier}-{number}.webp
SKINS: dict[int, list[tuple[str, str]]] = {
    1: [
        ("Синий кодер", "Синие иглы, серебристый ноутбук и кружка"),
        ("Огненный геймер", "Огненные иглы и красная игровая мышка"),
        ("Звёздная мечта", "Сиреневые иглы в звёздах и какао"),
        ("Росток", "Бирюзовые иглы и цветок в горшке"),
        ("Ночной ритм", "Чёрно-белые иглы и большие наушники"),
        ("Солнечный", "Жёлтые иглы и бабл-ти"),
        ("Котофей", "Розовые иглы и спящий котик"),
        ("Король кода", "Тёмно-малиновые иглы и стопка книг"),
        ("Морская волна", "Голубые иглы и бутылка воды"),
    ],
    2: [
        ("Радуга", "Радужные иглы и кружка с сердечком"),
        ("Лунный", "Иглы ночного неба и кружка с луной"),
        ("Пламя", "Красно-чёрные иглы и красный ноутбук"),
        ("Горный", "Серебристые иглы и горы на ноутбуке"),
        ("Лесной", "Зелёные иглы-листья и растение"),
        ("Меломан", "Пастельные иглы и фиолетовые наушники"),
        ("Космос", "Иглы-галактика и кружка с планетой"),
        ("Зефир", "Перламутровые иглы и розовый ноутбук"),
        ("Разряд", "Чёрно-зелёные иглы и молния"),
    ],
    3: [
        ("Мишка", "Синие иглы и кружка с медвежонком"),
        ("Огненная корона", "Огненные иглы и корона на ноутбуке"),
        ("Аметист", "Сиреневые иглы в искрах и бабл-ти"),
        ("Неоновый геймер", "Салатовые иглы и игровые наушники"),
        ("Ледяной", "Бело-голубые иглы и волна на ноутбуке"),
        ("Полночь", "Звёздные иглы и лампа-луна"),
        ("Малиновый", "Ярко-розовые иглы и кружка с сердцем"),
        ("Камуфляж", "Иглы цвета хаки и листик на ноутбуке"),
        ("Тень", "Чёрно-серые иглы, худи и горячий кофе"),
    ],
    4: [
        ("Ледник", "Синие иглы и кружка с ёжиком"),
        ("Киберспортсмен", "Огненные иглы и красные наушники"),
        ("Лавандовый", "Лавандовые иглы и котик на ноутбуке"),
        ("Банановый", "Лаймовые иглы и банан на ноутбуке"),
        ("Галактика", "Иглы в звёздах и лампа-луна"),
        ("Серебряный", "Серебристые иглы и белые наушники"),
        ("Сердечко", "Розовые иглы и кружка с сердцем"),
        ("Идея", "Чёрно-жёлтые иглы и лампочка"),
        ("Крутой", "Пастельные иглы и пиксельные очки"),
    ],
    5: [
        ("Классика", "Сине-фиолетовые иглы и ёжик на ноутбуке"),
        ("Закат", "Закатные иглы и кружка с ёжиком"),
        ("Облачный", "Белые иглы и наушники с ёжиком"),
        ("Лиственный", "Иглы из листьев и росток"),
        ("Звездопад", "Иглы звёздной ночи и тёмная бутылка"),
        ("Лунный кот", "Серые иглы и кружка-кот"),
        ("RGB", "Неоновые иглы и светящийся ноутбук"),
        ("Сакура", "Иглы в цветах сакуры и бабл-ти"),
        ("Цунами", "Иглы-волна и брызги воды"),
    ],
    6: [
        ("Сапфир", "Сапфировые иглы и сердечко на ноутбуке"),
        ("Феникс", "Огненные иглы и пламя на ноутбуке"),
        ("Стример", "Фиолетовые иглы и наушники с котом"),
        ("Мятный", "Зелёные иглы и росток"),
        ("Единорог", "Радужные пастельные иглы и бабл-ти"),
        ("Звездочёт", "Иглы-созвездие и лампа-луна"),
        ("Профессор", "Ледяные иглы, очки и стопка книг"),
        ("Токсичный", "Чёрно-лаймовые иглы и игровая мышка"),
        ("Рассвет", "Рассветные иглы и бутылка воды"),
    ],
}

# The retired clothing catalog. No longer sold: drawing clothes for every skin
# would cost too much. Rows are kept so that past purchases are not lost.
OLD_SKUS = (
    "cap_neon",
    "glasses_debug",
    "hoodie_python",
    "backpack_dev",
    "skin_neon",
    "skin_chrome",
    "vehicle_hogmobile",
    "home_capsule",
    "home_loft",
)


def seed_catalog(session: Session) -> int:
    """Add missing skins and retire old clothing. Safe to call repeatedly."""
    added = 0
    for tier, skins in SKINS.items():
        for number, (name, description) in enumerate(skins, start=1):
            sku = f"hog-{tier}-{number}"
            if session.scalar(select(Item).where(Item.sku == sku)):
                continue
            session.add(
                Item(
                    sku=sku,
                    name=name,
                    description=description,
                    slot=Slot.SKIN,
                    price=TIER_PRICES[tier],
                    asset_key=f"{tier}-{number}",
                    sort_order=tier * 100 + number,
                    tier=tier,
                )
            )
            added += 1
    for old_item in session.scalars(
        select(Item).where(Item.sku.in_(OLD_SKUS), Item.is_active.is_(True))
    ):
        old_item.is_active = False
    session.commit()
    return added
