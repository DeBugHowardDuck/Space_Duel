from __future__ import annotations

from dataclasses import dataclass

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackContext, AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngFixed:
    def random(self) -> float:
        return 0.0  # всегда попадаем

    def randint(self, a: int, b: int) -> int:
        return b  # максимальный урон для однозначности


def _mk(u_hull: int = 50, u_energy: int = 30) -> tuple[UnitClass, Weapon, Shield]:
    uclass = UnitClass(
        name="T", hull_max=u_hull, energy_max=u_energy, shield_mod=1.0, attack_mod=1.0
    )
    weapon = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=10,
        dmg_max=10,
        energy_cost=5,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    shield = Shield(slug="sh", name="SH", capacity=1000, efficiency=0.5, regen=0)
    return uclass, weapon, shield


def test_full_ignore_sends_all_damage_to_hull() -> None:
    uclass, weapon, shield = _mk()
    attacker = create_player(name="A", unit_class=uclass, weapon=weapon, shield=shield)
    target = create_ai(name="B", unit_class=uclass, weapon=weapon, shield=shield)
    target.shield_hp = 1000

    # Игнор щита 1.0: весь урон идёт в корпус
    ctx = AttackContext(
        damage_multiplier=1.0, extra_shield_ignore=1.0, shield_efficiency_factor=1.0
    )

    out = attacker.basic_attack(target, rng=RngFixed(), ctx=ctx)
    assert isinstance(out, AttackOutcome)
    assert out.hit is True
    assert out.damage_before_shield == 10
    assert out.shield_absorbed == 0
    assert out.hull_damage == 10


def test_full_shield_eff_absorbs_nonignored_until_hp_limit() -> None:
    uclass, weapon, shield = _mk()
    attacker = create_player(name="A", unit_class=uclass, weapon=weapon, shield=shield)
    target = create_ai(name="B", unit_class=uclass, weapon=weapon, shield=shield)
    target.shield_hp = 3  # щит слабый прямо сейчас

    # Эффективность щита 1.0, игнор 0.0 → вся nonignored часть уходит в щит, но не больше HP щита
    ctx = AttackContext(
        damage_multiplier=1.0, extra_shield_ignore=0.0, shield_efficiency_factor=2.0
    )  # clamp до 1.0

    out = attacker.basic_attack(target, rng=RngFixed(), ctx=ctx)
    assert isinstance(out, AttackOutcome)
    assert out.hit is True
    assert out.damage_before_shield == 10
    # Теоретически щит может съесть 10, но shield_hp=3 ⇒ фактически 3
    assert out.shield_absorbed == 3
    assert out.hull_damage == 7
