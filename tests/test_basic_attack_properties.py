from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hypothesis import (
    given,
    settings,
    strategies as st,
)

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngFixed:
    """Детерминированный RNG для контроля попаданий и урона."""

    r: float  # значение для random() ∈ [0,1)
    d: int  # значение для randint(a,b)

    def random(self) -> float:
        return self.r  # используем как бросок точности

    def randint(self, a: int, b: int) -> int:
        # игнорируем границы — мы гарантируем в тесте, что d попадёт в [a,b]
        return self.d


# Композитная стратегия: строим согласованный набор (атакующий, цель, RNG).
@st.composite
def units_and_rng(draw: st.DrawFn) -> tuple[Any, ...]:
    # dmg_min ≤ dmg_max
    dmg_min = draw(st.integers(min_value=1, max_value=20))
    dmg_max = draw(st.integers(min_value=dmg_min, max_value=dmg_min + 20))

    # фиксируем удар по урону в допустимом диапазоне
    d = draw(st.integers(min_value=dmg_min, max_value=dmg_max))

    # точность сделаем гарантированным попаданием (1.0), чтобы не зависеть от случайности
    accuracy = 1.0

    # стоимость энергии — разумная, и обеспечим, что энергия юнита ≥ cost
    energy_cost = draw(st.integers(min_value=0, max_value=15))

    # игнор щита 0..0.9
    shield_ignore = draw(
        st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False)
    )

    # ёмкость щита 0..25; эффективность 0..1
    shield_capacity = draw(st.integers(min_value=0, max_value=25))
    shield_eff = draw(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )

    # базовые параметры классов (без усилений, чтобы не усложнять свойство)
    hull_max = draw(st.integers(min_value=30, max_value=120))
    energy_max = draw(st.integers(min_value=energy_cost + 1, max_value=energy_cost + 40))

    uclass = UnitClass(
        name="TestClass",
        hull_max=hull_max,
        energy_max=energy_max,
        shield_mod=1.0,
        attack_mod=1.0,
    )

    weapon = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=dmg_min,
        dmg_max=dmg_max,
        energy_cost=energy_cost,
        shield_ignore=shield_ignore,
        accuracy=accuracy,
    )

    shield = Shield(
        slug="s",
        name="S",
        capacity=shield_capacity,
        efficiency=shield_eff,
        regen=0,
    )

    atk = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    tgt = create_ai(name="T", unit_class=uclass, weapon=weapon, shield=shield)

    # текущий запас щита цели — от 0 до capacity
    tgt.shield_hp = draw(st.integers(min_value=0, max_value=shield_capacity))

    # бросок точности — 0.0 (не важно при accuracy=1.0), бросок урона — d
    rng = RngFixed(r=0.0, d=d)

    return atk, tgt, rng


@given(units_and_rng())
@settings(max_examples=80)  # чуть сокращаем, чтобы тест шёл быстро локально
def test_basic_attack_invariants_hold(data: tuple[Any, ...]) -> None:
    atk, tgt, rng = data  # распаковали тройку из стратегии

    # снимем снимок до удара — проверим, что basic_attack не мутирует модели
    pre_attacker_energy = atk.energy
    pre_target_shield = tgt.shield_hp
    pre_target_hull = tgt.hull

    out = atk.basic_attack(tgt, rng=rng, ctx=None)

    # тип результата — строго AttackOutcome
    assert isinstance(out, AttackOutcome)

    # при достаточной энергии и accuracy=1.0 — всегда hit и списание энергии равно cost
    assert out.hit is True
    assert out.energy_spent == atk.weapon.energy_cost

    # неотрицательность и согласованность частей урона
    assert out.damage_before_shield >= 0
    assert out.shield_absorbed >= 0
    assert out.hull_damage >= 0
    assert out.shield_absorbed + out.hull_damage == out.damage_before_shield

    # поглощение не может превышать текущий запас щита цели (до применения)
    assert out.shield_absorbed <= pre_target_shield

    # спец-края: если эффективность 0 — щит не поглощает; если щит пуст — тоже 0
    if tgt.shield.efficiency == 0.0:
        assert out.shield_absorbed == 0
    if pre_target_shield == 0:
        assert out.shield_absorbed == 0

    # basic_attack НЕ мутирует состояние (это делает Arena.attack)
    assert atk.energy == pre_attacker_energy
    assert tgt.shield_hp == pre_target_shield
    assert tgt.hull == pre_target_hull
