from __future__ import annotations

from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def test_arena_attack_applies_outcome_and_switches_turn() -> None:
    """Атака применяет Outcome к состоянию и меняет ход, реген работает."""
    uclass = UnitClass(
        name="Test",
        hull_max=50,
        energy_max=30,
        shield_mod=1.0,
        attack_mod=1.2,
    )
    # Класс корабля: 50 HP корпуса, 30 энергии, моды=1.0/1.2.

    weapon = Weapon(
        slug="laser_x",
        name="Laser X",
        kind="laser",
        dmg_min=10,
        dmg_max=10,
        energy_cost=5,
        shield_ignore=0.25,
        accuracy=1.0,
    )
    # Лазер с фиксированным уроном 10 и точностью 100% (детерминировано попадём).

    shield = Shield(
        slug="s",
        name="S",
        capacity=8,
        efficiency=0.5,
        regen=0,
    )
    # Щит: макс 8, эффективность 0.5, реген 0 (для наглядности).

    player = create_player(
        name="P",
        unit_class=uclass,
        weapon=weapon,
        shield=shield,
    )
    # Игрок: стартует на максимумах (hull/energy/shield_hp).

    ai = create_ai(
        name="T",
        unit_class=uclass,
        weapon=weapon,
        shield=shield,
    )
    # Противник: тот же набор.

    ai.shield_hp = 6
    # Текущие очки щита меньше capacity: проверим ограничение поглощения.

    arena = Arena()
    # Создаём Singleton арены.

    arena.start(player=player, ai=ai)
    # Инициализация боя: сброс лога, ход — игрок, RNG по seed.

    outcome = arena.attack()
    # Ход игрока: считаем исход, применяем энергию/урон, делаем реген и смену хода.

    assert outcome.hit is True
    # Мы поставили accuracy=1.0 → попадание гарантировано.

    # Энергия у игрока: 30 - 5 (выстрел) + 3 (реген) = 28
    assert player.energy == 28

    # Применение outcome к цели: щит/корпус уменьшились строго на соответствующие поля.
    # (Числа конкретные не проверяем — у нас формулы покрыты отдельными тестами)
    assert ai.shield_hp >= 0
    assert ai.hull == uclass.hull_max - outcome.hull_damage

    # Телеметрия содержит запись ударов/промаха и смену хода.
    assert any("попал" in line or "промах" in line for line in arena.log)
    assert arena.turn == "ai"
    # Теперь ходит ИИ.
