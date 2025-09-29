from __future__ import annotations

from dataclasses import dataclass

import hypothesis.strategies as st
from hypothesis import given, settings

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackContext, AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngHitMid:
    """RNG: бросок точности 0.3 и серединный урон."""

    def random(self) -> float:
        return 0.3

    def randint(self, a: int, b: int) -> int:
        return (a + b) // 2


@given(
    dmg_min=st.integers(min_value=1, max_value=30),
    span=st.integers(min_value=0, max_value=20),
    energy_cost=st.integers(min_value=0, max_value=10),
    hull_max=st.integers(min_value=10, max_value=100),
    energy_max=st.integers(min_value=10, max_value=50),
    attack_mod=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    shield_capacity=st.integers(min_value=0, max_value=50),
    shield_eff=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    shield_mod=st.floats(min_value=0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    dmgx=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    ignore_add=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    shield_eff_mult=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_attack_invariants_hold(
    dmg_min: int,
    span: int,
    energy_cost: int,
    hull_max: int,
    energy_max: int,
    attack_mod: float,
    shield_capacity: int,
    shield_eff: float,
    shield_mod: float,
    dmgx: float,
    ignore_add: float,
    shield_eff_mult: float,
) -> None:
    dmg_max = dmg_min + span
    energy_max = max(energy_max, energy_cost)  # гарантируем потенциальную возможность выстрела

    uclass = UnitClass(
        name="T",
        hull_max=hull_max,
        energy_max=energy_max,
        shield_mod=shield_mod,
        attack_mod=attack_mod,
    )
    weapon = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=dmg_min,
        dmg_max=dmg_max,
        energy_cost=energy_cost,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    shield = Shield(slug="sh", name="SH", capacity=shield_capacity, efficiency=shield_eff, regen=0)

    attacker = create_player(name="A", unit_class=uclass, weapon=weapon, shield=shield)
    target = create_ai(name="B", unit_class=uclass, weapon=weapon, shield=shield)
    target.shield_hp = shield_capacity

    ctx = AttackContext(
        damage_multiplier=dmgx,
        extra_shield_ignore=ignore_add,
        shield_efficiency_factor=shield_eff_mult,
    )

    out = attacker.basic_attack(target, rng=RngHitMid(), ctx=ctx)
    assert isinstance(out, AttackOutcome)

    # Базовые инварианты — всегда
    assert out.energy_spent in (0, weapon.energy_cost)
    assert out.damage_before_shield >= 0
    assert out.shield_absorbed >= 0
    assert out.hull_damage >= 0
    assert out.shield_absorbed <= shield_capacity

    # Если энергии нет (хотя мы постарались обеспечить) — это явно отражается в результате
    if attacker.energy < weapon.energy_cost:
        assert out.hit is False
        assert out.energy_spent == 0
        return

    # Энергии хватило — проверяем корректность в обеих ветках
    if out.hit:
        assert out.energy_spent == weapon.energy_cost
        # Суммы должны сходиться при попадании
        assert out.shield_absorbed + out.hull_damage == out.damage_before_shield
    else:
        # При промахе уроновые поля равны нулю (по контракту basic_attack)
        assert out.damage_before_shield == 0
        assert out.shield_absorbed == 0
        assert out.hull_damage == 0
