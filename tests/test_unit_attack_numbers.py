from __future__ import annotations

from dataclasses import dataclass

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackContext, AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngFixed:
    """RNG с фиксированными значениями для точной проверки."""

    r: float
    d: int

    def random(self) -> float:
        return self.r

    def randint(self, a: int, b: int) -> int:
        # игнорируем a,b и возвращаем фиксированный урон в допустимом диапазоне
        return self.d


def test_attack_calculation_example() -> None:
    # Класс: атака = 1.2, щит-мод = 1.0
    uclass = UnitClass(name="Test", hull_max=50, energy_max=30, shield_mod=1.0, attack_mod=1.2)
    # Оружие: урон 10..10 (фикс), игнор 0.25, точность 100%
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
    # Щит: ёмкость 8, эффективность 0.5
    shield = Shield(slug="s", name="S", capacity=8, efficiency=0.5, regen=0)

    atk = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    tgt = create_ai(name="T", unit_class=uclass, weapon=weapon, shield=shield)
    tgt.shield_hp = 6  # текущая ёмкость меньше capacity, проверяем ограничение

    # Overcharge x1.5, EMP ослабляет щит до 0.8 (shield_eff*), доп. игнор 0.05
    ctx = AttackContext(
        damage_multiplier=1.5,
        extra_shield_ignore=0.05,
        shield_efficiency_factor=0.8,
    )

    out = atk.basic_attack(tgt, rng=RngFixed(r=0.0, d=10), ctx=ctx)
    assert isinstance(out, AttackOutcome)
    assert out.hit is True
    assert out.energy_spent == 5

    # Расчёт по строкам (для самопроверки):
    # dmg_roll=10; mod = 10 * 1.2 * 1.5 = 18 → округляем 18
    # ignore = 0.25 + 0.05 = 0.30; nonignored = 18 * 0.70 = 12.6 → 13 (round)
    # ignored_direct = 5; eff_shield = 0.5 * 1.0 * 0.8 = 0.4
    # shield_absorb_potential = 13 * 0.4 = 5.2 → 5; shield_hp=6 ⇒ shield_absorbed=5
    # hull_from_nonignored = 13 - 5 = 8; hull_damage = 8 + 5 = 13
    assert out.damage_before_shield == 18
    assert out.shield_absorbed == 5
    assert out.hull_damage == 13
    assert out.shield_absorbed + out.hull_damage == out.damage_before_shield
