from __future__ import annotations

import random

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackOutcome, create_ai, create_player


def test_basic_attack_no_energy_branch() -> None:
    u = UnitClass(name="T", hull_max=30, energy_max=5, shield_mod=1.0, attack_mod=1.0)
    w = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=5,
        dmg_max=5,
        energy_cost=7,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    s = Shield(slug="s", name="S", capacity=0, efficiency=0.0, regen=0)
    p = create_player(name="P", unit_class=u, weapon=w, shield=s)
    e = create_ai(name="E", unit_class=u, weapon=w, shield=s)
    p.energy = 0

    rng = random.Random(0)
    out = p.basic_attack(e, rng=rng, ctx=None)

    assert isinstance(out, AttackOutcome)
    assert out.hit is False
    assert out.energy_spent == 0
    assert e.hull == e.hull_max and e.shield_hp == 0
