from __future__ import annotations

from dataclasses import dataclass

from app.arena import Arena, ArenaConfig
from app.classes import UnitClass
from app.equipment import Shield, Weapon
from app.unit import AttackOutcome, create_ai, create_player


@dataclass(slots=True)
class RngScript:
    rnd: list[float]
    dmg_fixed: int | None = None

    def random(self) -> float:
        if self.rnd:
            return self.rnd.pop(0)
        return 0.0

    def randint(self, a: int, b: int) -> int:
        if self.dmg_fixed is not None:
            return self.dmg_fixed
        return (a + b) // 2


def test_ai_overcharge_applies_multiplier_and_spends_energy() -> None:
    # Сцена: чтобы видеть бафф, выключим эффект щита (efficiency=0.0)
    uclass = UnitClass(name="Test", hull_max=60, energy_max=50, shield_mod=1.0, attack_mod=1.0)
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
    shield = Shield(slug="sh", name="SH", capacity=100, efficiency=0.0, regen=0)

    player = create_player(name="P", unit_class=uclass, weapon=weapon, shield=shield)
    ai = create_ai(name="AI", unit_class=uclass, weapon=weapon, shield=shield)

    arena = Arena()
    # Жёстко задаём конфиг для теста: шанс скилла 100%, множитель Overcharge 1.5
    arena._config = ArenaConfig(
        energy_regen_per_turn=3,
        rng_seed=None,
        ai_skill_chance=1.0,
        overcharge_damage_mult=1.5,
        emp_shield_eff_factor=0.5,
        emp_extra_ignore=0.0,
    )
    # Сценарий RNG:
    #   random() -> 0.0  => пройдём шанс (<=1.0)
    #   random() -> 0.0  => выбор скилла: overcharge (choice < 0.5)
    #   random() -> 0.0  => попадание (accuracy=1.0 всё равно попали)
    #   randint() -> 10  => урон фикс 10
    arena.start(player=player, ai=ai)
    arena._rng = RngScript(rnd=[0.0, 0.0, 0.0], dmg_fixed=10)

    # Ход игрока (первый) — просто выстрел, чтобы передать ход ИИ
    arena.attack()
    assert arena.turn == "ai"

    # Ход ИИ — обязан скастовать Overcharge и ударить с множителем
    out: AttackOutcome = arena.attack()
    assert out.hit is True
    assert out.damage_before_shield == int(round(10 * arena._config.overcharge_damage_mult))

    # Энергия ИИ: 50 - 20(скилл) - 5(выстрел) + 3(реген конца хода) = 28
    # (стоимость Overcharge = 20 из реализации скилла)
    assert ai.energy == 28

    # Телеметрия содержит строку про использование скилла
    assert any("Overcharge" in line for line in arena.log)
