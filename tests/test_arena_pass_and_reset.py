from __future__ import annotations

import os
from typing import Any

from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def _mk_pair() -> tuple[Any, Any]:
    uclass = UnitClass(name="T", hull_max=40, energy_max=20, shield_mod=1.0, attack_mod=1.0)
    weapon = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=5,
        dmg_max=5,
        energy_cost=3,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    shield = Shield(slug="s", name="S", capacity=6, efficiency=0.5, regen=1)
    return (
        create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield),
        create_ai(name="E", unit_class=uclass, weapon=weapon, shield=shield),
    )


def test_pass_turn_regen_and_swap() -> None:
    os.environ["AI_SKILL_CHANCE"] = "0"
    arena = Arena()
    arena.reset()
    p, e = _mk_pair()
    arena.start(player=p, ai=e)

    p.energy = 0
    p.shield_hp = 0
    e.energy = 0
    e.shield_hp = 0

    before: str = arena.turn
    arena.pass_turn()
    after: str = arena.turn

    assert after != before

    assert 0 < p.energy <= p.energy_max
    assert 0 < e.energy <= e.energy_max
    assert 0 <= p.shield_hp <= p.shield.capacity
    assert 0 <= e.shield_hp <= e.shield.capacity
    assert any("пропуск хода" in line for line in arena.log)


def test_reset_clears_state() -> None:
    os.environ["AI_SKILL_CHANCE"] = "0"
    arena = Arena()
    arena.reset()
    p, e = _mk_pair()
    arena.start(player=p, ai=e)

    arena.reset()
    assert arena.turn == "player"
    assert not arena.is_initialized
