from __future__ import annotations

import os
from typing import Any

from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def _mk_pair() -> tuple[Any, Any]:
    uclass = UnitClass(name="T", hull_max=60, energy_max=50, shield_mod=1.0, attack_mod=1.0)
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
    shield = Shield(slug="s", name="S", capacity=20, efficiency=0.6, regen=0)
    return (
        create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield),
        create_ai(name="E", unit_class=uclass, weapon=weapon, shield=shield),
    )


def test_overcharge_increases_pre_shield_damage() -> None:
    os.environ["AI_SKILL_CHANCE"] = "0"
    os.environ["ARENA_RNG_SEED"] = "123"

    a1 = Arena()
    a1.reset()
    p1, e1 = _mk_pair()
    a1.start(player=p1, ai=e1)
    out_normal = a1.attack()

    a2 = Arena()
    a2.reset()
    p2, e2 = _mk_pair()
    a2.start(player=p2, ai=e2)
    out_skill = a2.attack_with_player_skill("overcharge")

    assert out_skill.damage_before_shield >= out_normal.damage_before_shield


def test_emp_reduces_shield_absorb() -> None:
    os.environ["AI_SKILL_CHANCE"] = "0"
    os.environ["ARENA_RNG_SEED"] = "456"

    a1 = Arena()
    a1.reset()
    p1, e1 = _mk_pair()
    a1.start(player=p1, ai=e1)
    out_normal = a1.attack()

    a2 = Arena()
    a2.reset()
    p2, e2 = _mk_pair()
    a2.start(player=p2, ai=e2)
    out_emp = a2.attack_with_player_skill("emp")

    assert out_emp.shield_absorbed <= out_normal.shield_absorbed
