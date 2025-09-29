from __future__ import annotations

from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def test_create_player_initial_resources() -> None:
    uclass = UnitClass(
        name="Interceptor", hull_max=40, energy_max=25, shield_mod=1.1, attack_mod=1.0
    )
    weapon = Weapon(
        slug="laser_mk1",
        name="Laser MK1",
        kind="laser",
        dmg_min=8,
        dmg_max=14,
        energy_cost=10,
        shield_ignore=0.10,
        accuracy=0.85,
    )
    shield = Shield(slug="shield_basic", name="Basic", capacity=30, efficiency=0.6, regen=3)

    unit = create_player(name="Alpha", unit_class=uclass, weapon=weapon, shield=shield)

    assert unit.controller == "player"
    assert unit.hull == uclass.hull_max
    assert unit.energy == uclass.energy_max
    assert unit.shield_hp == shield.capacity
    assert unit.skill_used is False


def test_create_ai_initial_resources() -> None:
    uclass = UnitClass(name="Destroyer", hull_max=55, energy_max=20, shield_mod=0.9, attack_mod=1.2)
    weapon = Weapon(
        slug="railgun_mk1",
        name="Railgun MK1",
        kind="railgun",
        dmg_min=12,
        dmg_max=20,
        energy_cost=14,
        shield_ignore=0.25,
        accuracy=0.75,
    )
    shield = Shield(slug="shield_heavy", name="Heavy", capacity=45, efficiency=0.7, regen=2)

    unit = create_ai(name="Omega", unit_class=uclass, weapon=weapon, shield=shield)

    assert unit.controller == "ai"
    assert unit.hull == uclass.hull_max
    assert unit.energy == uclass.energy_max
    assert unit.shield_hp == shield.capacity


def test_clamp_state_caps_value() -> None:
    uclass = UnitClass(name="Scout", hull_max=30, energy_max=18, shield_mod=1.0, attack_mod=0.9)
    weapon = Weapon(
        slug="laser_mk1",
        name="Laser MK1",
        kind="laser",
        dmg_min=8,
        dmg_max=14,
        energy_cost=10,
        shield_ignore=0.10,
        accuracy=0.85,
    )

    shield = Shield(slug="shield_basic", name="Basic", capacity=25, efficiency=0.5, regen=2)
    unit = create_player(name="Beta", unit_class=uclass, weapon=weapon, shield=shield)

    unit.hull = 999
    unit.energy = -5
    unit.shield_hp = 999

    unit.clamp_state()

    assert unit.hull == uclass.hull_max
    assert unit.energy == 0
    assert unit.shield_hp == shield.capacity
