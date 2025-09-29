import os

from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def test_hull_never_increases_midfight():
    os.environ["AI_SKILL_CHANCE"] = "0"
    a = Arena()
    a.reset()
    cls = UnitClass(name="T", hull_max=40, energy_max=20, shield_mod=1.0, attack_mod=1.0)
    w = Weapon(
        slug="w",
        name="W",
        kind="laser",
        dmg_min=5,
        dmg_max=5,
        energy_cost=3,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    s = Shield(slug="s", name="S", capacity=6, efficiency=0.5, regen=1)
    p = create_player("P", cls, w, s)
    e = create_ai("E", cls, w, s)
    a.start(p, e)

    for _ in range(5):
        before_p, before_e = p.hull, e.hull
        a.attack()  # текущий ход атакующего
        # корпус не должен превышать прошлое значение
        assert p.hull <= before_p
        assert e.hull <= before_e
        a.pass_turn()
        a.pass_turn()
