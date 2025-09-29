from app.arena import Arena
from app.unit import create_ai, create_player


def _arena_ready():
    a = Arena()
    a.reset()
    p = create_player()
    e = create_ai()
    a.start(p, e)
    return a, p, e


def test_ai_emp_when_player_has_shield():
    a, p, e = _arena_ready()
    a._swap_turn()
    e.energy = 999
    prev_shield = p.shield_hp
    a._ai_take_turn()
    assert a.turn == "player"
    assert p.shield_hp <= prev_shield


def test_ai_overcharge_when_player_low_hull():
    a, p, e = _arena_ready()
    a._swap_turn()
    e.energy = 999
    p.hull = int(0.3 * p.hull_max)
    prev_hull = p.hull
    a._ai_take_turn()
    assert a.turn == "player"
    assert p.hull <= prev_hull


def test_ai_shoots_normally_otherwise():
    a, p, e = _arena_ready()
    a._swap_turn()
    e.energy = 999
    p.shield_hp = 0
    p.hull = p.hull_max
    prev_hull = p.hull
    a._ai_take_turn()
    assert a.turn == "player"
    assert p.hull <= prev_hull
