from __future__ import annotations

from dataclasses import dataclass

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackContext, AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngStub:
    seq: list[float]

    def random(self) -> float:
        if self.seq:
            return self.seq.pop(0)
        return 0.999

    def randint(self, a: int, b: int) -> int:
        return a


def _mk_sample() -> tuple[UnitClass, Weapon, Shield]:
    uclass = UnitClass(name="Test", hull_max=30, energy_max=20, shield_mod=1.0, attack_mod=1.0)
    weapon = Weapon(
        slug="laser_mk1",
        name="Laser",
        kind="laser",
        dmg_min=8,
        dmg_max=12,
        energy_cost=10,
        shield_ignore=0.1,
        accuracy=0.6,
    )
    shield = Shield(slug="shield_basic", name="Basic", capacity=15, efficiency=0.6, regen=2)
    return uclass, weapon, shield


def test_basic_attack_hit_and_miss() -> None:
    uclass, weapon, shield = _mk_sample()
    attacker = create_player(name="A", unit_class=uclass, weapon=weapon, shield=shield)
    target = create_ai(name="B", unit_class=uclass, weapon=weapon, shield=shield)

    hit_out = attacker.basic_attack(target, rng=RngStub([0.5]), ctx=AttackContext())
    assert isinstance(hit_out, AttackOutcome)
    assert hit_out.hit is True
    assert hit_out.energy_spent == weapon.energy_cost
    assert 0.0 <= hit_out.accuracy_roll < 1.0

    miss_out = attacker.basic_attack(target, rng=RngStub([0.9]), ctx=AttackContext())
    assert miss_out.hit is False
    assert miss_out.energy_spent == weapon.energy_cost

    assert attacker.energy == uclass.energy_max


def test_cannot_fire_without_energy() -> None:
    uclass, weapon, shield = _mk_sample()
    attacker = create_player(name="A", unit_class=uclass, weapon=weapon, shield=shield)
    target = create_ai(name="B", unit_class=uclass, weapon=weapon, shield=shield)

    # Обнулим энергию вручную
    attacker.energy = 0
    out = attacker.basic_attack(target, rng=RngStub([0.0]), ctx=AttackContext())

    assert out.hit is False
    assert out.energy_spent == 0
    assert "Недостаточно энергии" in out.notes[0]
