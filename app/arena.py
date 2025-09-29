from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import ClassVar, Literal

from app.classes import CLASS_REGISTRY, UnitClass, register_unit_class
from app.skills import create_skill
from app.unit import (
    AIUnit,
    AttackContext,
    AttackOutcome,
    PlayerUnit,
    RandomSource,
)


@dataclass(frozen=True, slots=True)
class ArenaConfig:
    """Параметры арены."""

    energy_regen_per_turn: int = 3
    rng_seed: int | None = None
    ai_skill_chance: float = 0.10
    overcharge_damage_mult: float = 1.50
    emp_shield_eff_factor: float = 0.50
    emp_extra_ignore: float = 0.00


class Arena:
    """
    Singleton арены: хранит состояние боя, применяет результаты атак, ведёт телеметрию.
    """

    _instance: ClassVar[Arena | None] = None

    # Профиль сложности Бота - влияет на пороги применения рещений
    ai_difficulty: Literal["easy", "normal", "hard"] = "normal"

    def __new__(cls) -> Arena:
        """
        Реализация Singleton: создаём один раз, потом всегда возвращаем его.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._player: PlayerUnit | None = None
        self._ai: AIUnit | None = None
        self._turn: Literal["player", "ai"] = "player"
        self._log: list[str] = []
        self._rng: RandomSource = random.Random()
        self.cooldowns: dict[str, dict[str, int]] = {
            "player": {"overcharge": 0, "emp": 0},
            "ai": {"overcharge": 0, "emp": 0},
        }

        seed_env = os.getenv("ARENA_RNG_SEED")
        seed: int | None = int(seed_env) if seed_env and seed_env.isdigit() else None

        skill_p_env = os.getenv("AI_SKILL_CHANCE")
        try:
            skill_p = float(skill_p_env) if skill_p_env is not None else 0.10
        except ValueError:
            skill_p = 0.10
        if skill_p < 0.0:
            skill_p = 0.0
        if skill_p > 1.0:
            skill_p = 1.0

        self._config: ArenaConfig = ArenaConfig(
            energy_regen_per_turn=3,
            rng_seed=seed,
            ai_skill_chance=skill_p,
            overcharge_damage_mult=1.50,
            emp_shield_eff_factor=0.50,
            emp_extra_ignore=0.00,
        )

    @property
    def log(self) -> tuple[str, ...]:
        return tuple(self._log)

    @property
    def turn(self) -> Literal["player", "ai"]:
        """Чей сейчас ход: 'player' или 'ai'."""
        return self._turn

    @property
    def player(self) -> PlayerUnit:
        """Безопасный доступ к игроку."""
        assert self._player is not None, "Бой не инициализирован: player=None"
        return self._player

    @property
    def ai(self) -> AIUnit:
        """Безопасный доступ к противнику (с проверкой инициализации боя)."""
        assert self._ai is not None, "Бой не инициализирован: ai=None"
        return self._ai

    @property
    def is_initialized(self) -> bool:
        """True, если оба участника боя назначены."""
        return (self._player is not None) and (self._ai is not None)

    def start(
        self,
        player: PlayerUnit,
        ai: AIUnit,
        *,
        difficulty: Literal["easy", "normal", "hard"] = "normal",
    ) -> None:
        """
        Старт боя:
        - устанавливает участников;
        - сбрасывает ход, логи;
        - пересеет RNG по конфигу (для воспроизводимости).
        """
        self._player = player
        self._ai = ai
        self.ai_difficulty = difficulty
        self._turn = "player"
        self._log.clear()
        self._rng = random.Random(self._config.rng_seed)
        self._log.append("Бой начался. Ход игрока.")
        self.cooldowns["player"].update(overcharge=0, emp=0)
        self.cooldowns["ai"].update(overcharge=0, emp=0)

    @property
    def is_finished(self) -> bool:
        """Бой завершён, если у кого-то корпус опустился до 0."""
        return not self.player.is_alive or not self.ai.is_alive

    @property
    def ui_log(self) -> tuple[str, ...]:
        visible: list[str] = []
        for line in self._log:
            if line.startswith("[SNAP:"):
                continue
            if "реген" in line.lower():  # убираем шум про реген
                continue
            visible.append(line)
        return tuple(visible)

    def attack(self) -> AttackOutcome:
        """
        Выполняет выстрел текущего атакующего по защищающемуся:
        1) считает исход через BaseUnit.basic_attack;
        2) применяет списание энергии, урон по щиту/корпусу;
        3) регенит ресурсы конца хода у обеих сторон;
        4) переключает ход.
        """
        attacker, defender = self._attacker_defender()

        ctx: AttackContext = self._maybe_apply_ai_skill(attacker, defender)
        outcome: AttackOutcome = attacker.basic_attack(
            defender,
            rng=self._rng,
            ctx=ctx,
        )

        if outcome.energy_spent > 0:
            attacker.spend_energy(outcome.energy_spent)

        if outcome.hit:
            if outcome.shield_absorbed > 0:
                defender.shield_hp -= outcome.shield_absorbed
                if defender.shield_hp < 0:
                    defender.shield_hp = 0

            if outcome.hull_damage > 0:
                defender.hull -= outcome.hull_damage
                if defender.hull < 0:
                    defender.hull = 0

        self._log_outcome(attacker_name=attacker.name, outcome=outcome)

        self._snapshot("after-damage")
        self._end_of_turn_regen()
        self._snapshot("after-regen")

        if not self.is_finished:
            self._swap_turn()
        self._snapshot("after-swap")
        return outcome

    def pass_turn(self) -> None:
        """Текущий ход пропускается: копим ресурсы, пишем лог, переключаемся."""
        self._log.append(f"{self._turn}: пропуск хода.")
        self._snapshot("before-pass-regen")
        self._end_of_turn_regen()
        self._snapshot("after-pass-regen")

        if not self.is_finished:
            self._swap_turn()
        self._snapshot("after-pass-swap")

    def attack_with_player_skill(self, slug: str) -> AttackOutcome | None:
        if self.is_finished or self.turn != "player":
            return None
        if slug not in {"overcharge", "emp"}:
            return None
        if not self._cd_ready("player", slug):
            self._log.append(f"Скилл {slug} на перезарядке.")
            return None

        attacker, defender = self._attacker_defender()
        ctx = self._apply_player_skill(attacker, defender, slug)
        outcome = attacker.basic_attack(defender, rng=self._rng, ctx=ctx)

        if outcome.energy_spent > 0:
            attacker.spend_energy(outcome.energy_spent)
        if outcome.hit:
            if outcome.shield_absorbed > 0:
                defender.shield_hp = max(0, defender.shield_hp - outcome.shield_absorbed)
            if outcome.hull_damage > 0:
                defender.hull = max(0, defender.hull - outcome.hull_damage)

        self._log_outcome(attacker_name=attacker.name, outcome=outcome)
        self._end_of_turn_regen()
        if not self.is_finished:
            self._swap_turn()

        self._cd_set("player", slug, 2)
        self._cd_tick()
        return outcome

    def _snapshot(self, label: str) -> None:
        p = self.player
        a = self.ai
        self._log.append(
            f"[SNAP:{label}] turn={self._turn} | "
            f"P(hull={p.hull}/{p.hull_max}, sh={p.shield_hp}/{p.shield.capacity}, en={p.energy}/{p.energy_max}) | "
            f"A(hull={a.hull}/{a.hull_max}, sh={a.shield_hp}/{a.shield.capacity}, en={a.energy}/{a.energy_max})"
        )

    def _ai_take_turn(self) -> None:
        if self.is_finished or self.turn != "ai":
            return

        ai = self.ai
        p = self.player

        # Пороговое значение по сложности
        # EMP: насколько «толстый» щит у игрока считаем поводом жать EMP (в очках щита)

        emp_shield_threshold = {
            "easy": 15,
            "normal": 8,
            "hard": 1,
        }[self.ai_difficulty]

        # Overcharge: добивка при низком hull игрока.

        over_hull_pct = {
            "easy": 0.25,
            "normal": 0.35,
            "hard": 0.45,
        }[self.ai_difficulty]

        # нет энергии → пасс
        if not ai.can_fire():
            self.pass_turn()
            self._cd_tick()
            return

        # EMP по щиту
        if p.shield_hp > emp_shield_threshold and self._cd_ready("ai", "emp") and ai.energy >= 25:
            slug = "emp"
            skill = create_skill(slug)
            if skill.can_use(ai):
                result = skill.execute(ai, p)
                if result.energy_spent > 0:
                    ai.spend_energy(result.energy_spent)

                ctx = AttackContext(
                    damage_multiplier=1.0,
                    extra_shield_ignore=self._config.emp_extra_ignore,
                    shield_efficiency_factor=self._config.emp_shield_eff_factor,
                )
                outcome = ai.basic_attack(p, rng=self._rng, ctx=ctx)

                if outcome.energy_spent > 0:
                    ai.spend_energy(outcome.energy_spent)
                if outcome.hit:
                    if outcome.shield_absorbed > 0:
                        p.shield_hp = max(0, p.shield_hp - outcome.shield_absorbed)
                    if outcome.hull_damage > 0:
                        p.hull = max(0, p.hull - outcome.hull_damage)

                self._log_outcome(attacker_name=ai.name, outcome=outcome)
                self._end_of_turn_regen()
                if not self.is_finished:
                    self._swap_turn()

                self._cd_set("ai", slug, 2)
                self._cd_tick()
                return

        # Overcharge добивающий
        if (
            self._cd_ready("ai", "overcharge")
            and ai.energy >= 20
            and p.hull <= int(0.35 * p.hull_max)
        ):
            if (
                self._cd_ready("ai", "overcharge")
                and ai.energy >= 20
                and p.hull <= int(over_hull_pct * p.hull_max)
            ):
                slug = "overcharge"
                skill = create_skill(slug)
                if skill.can_use(ai):
                    result = skill.execute(ai, p)
                    if result.energy_spent > 0:
                        ai.spend_energy(result.energy_spent)

                    ctx = AttackContext(
                        damage_multiplier=self._config.overcharge_damage_mult,
                        extra_shield_ignore=0.0,
                        shield_efficiency_factor=1.0,
                    )
                    outcome = ai.basic_attack(p, rng=self._rng, ctx=ctx)

                    if outcome.energy_spent > 0:
                        ai.spend_energy(outcome.energy_spent)
                    if outcome.hit:
                        if outcome.shield_absorbed > 0:
                            p.shield_hp = max(0, p.shield_hp - outcome.shield_absorbed)
                        if outcome.hull_damage > 0:
                            p.hull = max(0, p.hull - outcome.hull_damage)

                    self._log_outcome(attacker_name=ai.name, outcome=outcome)
                    self._end_of_turn_regen()
                    if not self.is_finished:
                        self._swap_turn()

                    self._cd_set("ai", slug, 2)
                    self._cd_tick()
                    return

        self.attack()
        self._cd_tick()

    def _apply_player_skill(
        self,
        attacker: PlayerUnit | AIUnit,
        defender: PlayerUnit | AIUnit,
        slug: str,
    ) -> AttackContext:
        # только игрок и только если ещё не использовал
        if attacker.controller != "player" or attacker.skill_used:
            return AttackContext()
        if slug not in {"overcharge", "emp"}:
            self._log.append(f"player: неизвестный скилл '{slug}'")
            return AttackContext()

        skill = create_skill(slug)
        if not skill.can_use(attacker):
            self._log.append(f"player: попытка {skill.name}, но нет энергии Оо")
            return AttackContext()

        result = skill.execute(attacker, defender)
        if not result.success:
            self._log.append(f"player: использует {result.description}")
            return AttackContext()

        if result.energy_spent > 0:
            attacker.spend_energy(result.energy_spent)
        attacker.mark_skill_used()

        if slug == "overcharge":
            ctx = AttackContext(
                damage_multiplier=self._config.overcharge_damage_mult,
                extra_shield_ignore=0.0,
                shield_efficiency_factor=1.0,
            )
        else:  # emp
            ctx = AttackContext(
                damage_multiplier=1.0,
                extra_shield_ignore=self._config.emp_extra_ignore,
                shield_efficiency_factor=self._config.emp_shield_eff_factor,
            )

        self._log.append(f"player: использует {result.description}")
        return ctx

    def _maybe_apply_ai_skill(
        self,
        attacker: PlayerUnit | AIUnit,
        defender: PlayerUnit | AIUnit,
    ) -> AttackContext:
        # только бот и только если ещё не использовал скилл
        if attacker.controller != "ai" or attacker.skill_used:
            return AttackContext()

        # шанс на скилл
        if self._rng.random() >= self._config.ai_skill_chance:
            return AttackContext()

        slug = "overcharge" if self._rng.random() < 0.5 else "emp"
        skill = create_skill(slug)

        if not skill.can_use(attacker):
            self._log.append(f"ai: попытка {skill.name}, но недостаточно энергии")
            return AttackContext()

        result = skill.execute(attacker, defender)
        if not result.success:
            self._log.append(f"ai: использует {result.description}")
            return AttackContext()

        if result.energy_spent > 0:
            attacker.spend_energy(result.energy_spent)
        attacker.mark_skill_used()

        if slug == "overcharge":
            ctx = AttackContext(
                damage_multiplier=self._config.overcharge_damage_mult,
                extra_shield_ignore=0.0,
                shield_efficiency_factor=1.0,
            )
        else:
            ctx = AttackContext(
                damage_multiplier=1.0,
                extra_shield_ignore=self._config.emp_extra_ignore,
                shield_efficiency_factor=self._config.emp_shield_eff_factor,
            )

        self._log.append(f"ai использует {result.description}")
        return ctx

    def _attacker_defender(
        self,
    ) -> tuple[PlayerUnit | AIUnit, PlayerUnit | AIUnit]:
        """Возвращает пару (атакующий, защищающийся) согласно self._turn."""
        if self._turn == "player":
            return self.player, self.ai
        return self.ai, self.player

    def _swap_turn(self) -> None:
        """Переключает ход и пишет запись в лог."""
        self._turn = "ai" if self._turn == "player" else "player"
        self._log.append(f"Теперь ход: {self._turn}")

    def _end_of_turn_regen(self) -> None:
        regen = self._config.energy_regen_per_turn
        for unit in (self.player, self.ai):
            unit.regen_energy(regen)
            unit.regen_shield()
            # корпус не растёт и не уходит за границы
            if unit.hull > unit.hull_max:
                unit.hull = unit.hull_max
            if unit.hull < 0:
                unit.hull = 0

    def _log_outcome(self, attacker_name: str, outcome: AttackOutcome) -> None:
        """Добавляет в лог короткое описание результата хода атакующего."""
        if outcome.energy_spent == 0 and not outcome.hit:
            self._log.append(f"{attacker_name}: недостаточно энергии для выстрела")
            return

        if not outcome.hit:
            self._log.append(f"{attacker_name}: промах (энергия -{outcome.energy_spent})")
            return

        self._log.append(
            f"{attacker_name}: попал (энергия -{outcome.energy_spent}), "
            f"урон до щита {outcome.damage_before_shield}, "
            f"поглотил щит {outcome.shield_absorbed}, "
            f"корпусу {outcome.hull_damage}"
        )

    def reset(self) -> None:
        """Сбрасывает текущий бой."""
        self._player = None
        self._ai = None
        self._turn = "player"
        self._log.clear()
        self._rng = random.Random(self._config.rng_seed)
        self._log.append("Бой сброшен")

    def _cd_ready(self, side: str, slug: str) -> bool:
        return self.cooldowns.get(side, {}).get(slug, 0) <= 0

    def _cd_set(self, side: str, slug: str, turns: int) -> None:
        self.cooldowns[side][slug] = max(self.cooldowns[side].get(slug, 0), int(turns))

    def _cd_tick(self) -> None:
        for side in ("player", "ai"):
            for k, v in self.cooldowns[side].items():
                if v > 0:
                    self.cooldowns[side][k] = v - 1


def _ensure_sample_classes() -> None:
    if "interceptor" not in CLASS_REGISTRY:
        register_unit_class(
            "interceptor",
            UnitClass(
                name="Interceptor",
                hull_max=40,
                energy_max=25,
                shield_mod=1.1,
                attack_mod=1.0,
            ),
        )
    if "destroyer" not in CLASS_REGISTRY:
        register_unit_class(
            "destroyer",
            UnitClass(name="Destroyer", hull_max=55, energy_max=20, shield_mod=0.9, attack_mod=1.2),
        )


_ensure_sample_classes()
