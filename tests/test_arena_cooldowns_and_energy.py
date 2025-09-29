from app.arena import Arena
from app.classes import CLASS_REGISTRY, get_unit_class, register_unit_class
from app.unit import create_ai, create_player


def _ensure_classes():
    if "interceptor" not in CLASS_REGISTRY:
        register_unit_class("interceptor", get_unit_class("interceptor"))
    if "destroyer" not in CLASS_REGISTRY:
        register_unit_class("destroyer", get_unit_class("destroyer"))


def _fresh_arena():
    a = Arena()
    a.reset()
    _ensure_classes()
    p = create_player()
    e = create_ai()
    a.start(p, e)
    return a


def test_pass_regens_energy_and_shield():
    a = _fresh_arena()
    p = a.player
    p.energy = max(0, p.energy - 10)
    p.shield_hp = max(0, p.shield_hp - 5)
    a.pass_turn()
    assert p.energy >= min(p.energy_max, a._config.energy_regen_per_turn)
    assert 0 <= p.shield_hp <= p.shield.capacity


def test_player_overcharge_sets_cooldown_and_ticks():
    a = _fresh_arena()
    p = a.player
    p.energy = 999  # чтобы хватало
    assert a._cd_ready("player", "overcharge")
    a.attack_with_player_skill("overcharge")
    assert not a._cd_ready("player", "overcharge")
    assert a.cooldowns["player"]["overcharge"] in (1, 2)
