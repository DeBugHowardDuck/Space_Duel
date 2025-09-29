from app.arena import Arena
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import create_ai, create_player


def _mk_units():
    uclass = UnitClass(name="Test", hull_max=40, energy_max=50, shield_mod=1.0, attack_mod=1.0)
    # 100% попадание, фиксированный урон = 5, чтобы тесты не были флаки
    weapon = Weapon(
        slug="laser_test",
        name="Laser Test",
        kind="laser",
        dmg_min=5,
        dmg_max=5,
        energy_cost=10,
        shield_ignore=0.0,
        accuracy=1.0,
    )
    shield = Shield(slug="shield_test", name="Shield Test", capacity=20, efficiency=0.6, regen=0)
    return uclass, weapon, shield


def test_ai_uses_emp_when_player_has_shield():
    uclass, weapon, shield = _mk_units()
    player = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    ai = create_ai(name="AI", unit_class=uclass, weapon=weapon, shield=shield)

    arena = Arena()
    arena.start(player=player, ai=ai, difficulty="hard")

    # Игрок со щитом > 1 (на hard порог = 1)
    player.shield_hp = 12
    ai.energy = 30
    if arena.turn != "ai":
        arena._swap_turn()
    arena.cooldowns["ai"]["emp"] = 0

    arena._ai_take_turn()

    # Должны уйти в КД EMP, а ход перейти к игроку
    assert arena.cooldowns["ai"]["emp"] > 0
    assert arena.turn == "player"


def test_ai_uses_overcharge_when_player_shield_is_down():
    uclass, weapon, shield = _mk_units()
    player = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    ai = create_ai(name="AI", unit_class=uclass, weapon=weapon, shield=shield)

    arena = Arena()
    arena.start(player=player, ai=ai, difficulty="normal")

    # Щита у игрока нет; у ИИ энергии много; КД overcharge свободен
    player.shield_hp = 0
    player.hull = int(0.3 * player.hull_max)
    ai.energy = weapon.energy_cost + 25
    if arena.turn != "ai":
        arena._swap_turn()
    arena.cooldowns["ai"]["overcharge"] = 0


def test_ai_attacks_if_can_fire_and_no_skill_better():
    uclass, weapon, shield = _mk_units()
    player = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    ai = create_ai(name="AI", unit_class=uclass, weapon=weapon, shield=shield)

    arena = Arena()
    arena.start(player=player, ai=ai, difficulty="easy")

    player.shield_hp = 0
    ai.energy = weapon.energy_cost
    if arena.turn != "ai":
        arena._swap_turn()
    arena.cooldowns["ai"]["emp"] = 3
    arena.cooldowns["ai"]["overcharge"] = 2

    hull_before = player.hull
    arena._ai_take_turn()

    assert arena.turn == "player"
    assert player.hull == hull_before - 5
