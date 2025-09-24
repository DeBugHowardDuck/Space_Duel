from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import ClassVar, Literal

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
    # ↑ Статическая переменная класса: единственный экземпляр хранится здесь.

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
        """Возвращает немутируемую копию телеметрии."""
        return tuple(self._log)

    @property
    def turn(self) -> Literal["player", "ai"]:
        """Чей сейчас ход: 'player' или 'ai'."""
        return self._turn

    @property
    def player(self) -> PlayerUnit:
        """Безопасный доступ к игроку (с проверкой инициализации боя)."""
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

    def start(self, player: PlayerUnit, ai: AIUnit) -> None:
        """
        Старт боя:
        - устанавливает участников;
        - сбрасывает ход, логи;
        - пересеет RNG по конфигу (для воспроизводимости).
        """
        self._player = player
        self._ai = ai
        self._turn = "player"
        self._log.clear()
        self._rng = random.Random(self._config.rng_seed)
        self._log.append("Бой начался. Ход игрока.")

    @property
    def is_finished(self) -> bool:
        """Бой завершён, если у кого-то корпус (hull) опустился до 0."""
        return not self.player.is_alive or not self.ai.is_alive

    def attack(self) -> AttackOutcome:
        """
        Выполняет выстрел текущего атакующего по защищающемуся:
        1) считает исход через BaseUnit.basic_attack (без мутаций);
        2) применяет списание энергии, урон по щиту/корпусу;
        3) регенит ресурсы конца хода у обеих сторон;
        4) переключает ход (если бой не завершён).
        Возвращает AttackOutcome — удобно для UI/тестов.
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

        self._end_of_turn_regen()

        if not self.is_finished:
            self._swap_turn()

        return outcome

    def pass_turn(self) -> None:
        """Текущий ход пропускается: копим ресурсы, пишем лог, переключаемся."""
        who = self._turn
        # ↑ Сохраняем, кто пропускает (для текста лога).

        self._log.append(f"{who}: пропуск хода.")
        # ↑ Добавляем запись в телеметрию.

        self._end_of_turn_regen()
        # ↑ Реген в конце хода всё равно происходит.

        if not self.is_finished:
            self._swap_turn()
        # ↑ Меняем ход, если бой не закончился.

    def attack_with_player_skill(self, slug: str) -> AttackOutcome:
        """
        Ход игрока с применением скилла 'overcharge' или 'emp' прямо перед выстрелом.
        Поведение полностью зеркалит ИИ: энергия за скилл списывается сразу,
        эффект действует только на этот выстрел, флаг одноразового использования ставится.
        """
        assert self._turn == "player", "Сейчас не ход игрока"
        attacker, defender = self._attacker_defender()

        # Сформировать контекст по выбранному скиллу (или пустой, если нельзя/уже использован).
        ctx: AttackContext = self._apply_player_skill(attacker, defender, slug)

        # Дальше — тот же конвейер, что и в обычном attack()
        outcome: AttackOutcome = attacker.basic_attack(defender, rng=self._rng, ctx=ctx)

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
        self._end_of_turn_regen()
        if not self.is_finished:
            self._swap_turn()
        return outcome

    def _apply_player_skill(
        self,
        attacker: PlayerUnit | AIUnit,
        defender: PlayerUnit | AIUnit,
        slug: str,
    ) -> AttackContext:
        """
        Пробует применить скилл игрока и вернуть AttackContext.
        Если сейчас не игрок, скилл уже использован или энергии не хватает — вернёт пустой контекст.
        """
        # Только игрок, и только один раз за бой.
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
        else:
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
        """
        Если ход ИИ и скилл ещё не использован:
        - с вероятностью ai_skill_chance применяет Overcharge или EMP,
        - списывает энергию за скилл,
        - возвращает AttackContext с эффектом для текущего выстрела,
        - пишет запись в лог.
        Если условие не выполнено — возвращает пустой контекст (единичные множители).
        """
        # Игрок — не в этом методе; флаг «уже использован» у юнита защищает от повторов.
        if attacker.controller != "ai" or attacker.skill_used:
            return AttackContext()
        # Бросок шанса
        roll: float = self._rng.random()
        if roll >= self._config.ai_skill_chance:
            return AttackContext()
        # Выбор скилла: <0.5 → overcharge, иначе → emp
        choice: float = self._rng.random()
        slug: str = "overcharge" if choice < 0.5 else "emp"

        skill = create_skill(slug)

        # Проверка энергии на скилл.
        if not skill.can_use(attacker):
            self._log.append(f"ai: попытка {skill.name}, но недостаточно энергии")
            return AttackContext()

        # Использование скилла.
        result = skill.execute(attacker, defender)
        if not result.success:
            self._log.append(f"ai: использует {result.description}")
            return AttackContext()

        # Списываем энергию за скилл и помечаем одноразовае использование.
        if result.energy_spent > 0:
            attacker.spend_energy(result.energy_spent)
        attacker.mark_skill_used()

        # Сообщаем контекст выстрела согласно выбранного скилла.
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
        """Реген в конце хода: энергия (+config) и щит (по предмету) — у обеих сторон."""
        regen = self._config.energy_regen_per_turn
        # Сколько энергии добавить.

        self.player.regen_energy(regen)
        self.ai.regen_energy(regen)
        # Энергия обеим сторонам.

        self.player.regen_shield()
        self.ai.regen_shield()
        # Щит восстанавливается по предметам (capacity/regen уже учтены внутри).

    def _log_outcome(self, attacker_name: str, outcome: AttackOutcome) -> None:
        """Добавляет в лог короткое описание результата хода атакующего."""
        if outcome.energy_spent == 0 and not outcome.hit:
            self._log.append(f"{attacker_name}: недостаточно энергии для выстрела")
            return
        # Нет энергии — отдельное сообщение и выходим.

        if not outcome.hit:
            self._log.append(f"{attacker_name}: промах (энергия -{outcome.energy_spent})")
            return
        # Промах — фиксируем списанную энергию.

        self._log.append(
            f"{attacker_name}: попал (энергия -{outcome.energy_spent}), "
            f"урон до щита {outcome.damage_before_shield}, "
            f"поглотил щит {outcome.shield_absorbed}, "
            f"корпусу {outcome.hull_damage}"
        )
        # Попадание — выводим числа из AttackOutcome.

    def reset(self) -> None:
        """Сбрасывает текущий бой."""
        self._player = None
        self._ai = None
        self._turn = "player"
        self._log.clear()
        self._rng = random.Random(self._config.rng_seed)
        self._log.append("Бой сброшен")
