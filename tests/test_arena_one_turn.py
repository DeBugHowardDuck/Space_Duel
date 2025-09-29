from __future__ import annotations

import os

from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackOutcome, create_ai, create_player


def test_arena_attack_one_turn() -> None:
    # Заглушка скилов иишки.
    os.environ["AI_SKILL_CHANCE"] = "0"

    uclass = UnitClass(name="Test", hull_max=50, energy_max=30, shield_mod=1.0, attack_mod=1.2)

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

    shield = Shield(slug="s", name="S", capacity=8, efficiency=0.5, regen=0)

    atk = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    tgt = create_ai(name="T", unit_class=uclass, weapon=weapon, shield=shield)

    tgt.shield_hp = 6

    arena = Arena()
    arena.reset()
    arena.start(player=atk, ai=tgt)

    out = arena.attack()

    assert isinstance(out, AttackOutcome)
    assert out.hit is True
    assert out.energy_spent == 5

    assert out.damage_before_shield == 12
    assert out.shield_absorbed == 5
    assert out.hull_damage == 7
    assert out.shield_absorbed + out.hull_damage == out.damage_before_shield

    assert tgt.shield_hp == 1
    assert tgt.hull == 43
    assert atk.energy == 28
    assert tgt.energy == tgt.energy_max
    assert arena.turn == "ai"

    assert 0 <= atk.energy <= atk.energy_max
    assert 0 <= tgt.energy <= tgt.energy_max
    assert 0 <= tgt.shield_hp <= tgt.shield.capacity
    assert 0 <= tgt.hull <= tgt.hull_max
