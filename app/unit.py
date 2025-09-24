from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from typing import Literal, Protocol, overload

from app.classes import UnitClass
from app.equipment import Shield, Weapon


def _round_half_up(x: float) -> int:
    """Математическое округление: 0.5 → вверх."""
    return int(math.floor(x + 0.5))


# ---------- Источник случайности (для детерминируемых тестов) ----------


class RandomSource(Protocol):
    def random(self) -> float: ...
    def randint(self, a: int, b: int) -> int: ...


# ---------- Контексты/результаты атаки (чистые контейнеры данных) ----------


@dataclass(frozen=True, slots=True)
class AttackContext:
    damage_multiplier: float = 1.0
    extra_shield_ignore: float = 0.0
    shield_efficiency_factor: float = 1.0


@dataclass(frozen=True, slots=True)
class AttackOutcome:
    hit: bool
    energy_spent: int
    accuracy_roll: float
    weapon_slug: str
    notes: tuple[str, ...] = ()
    raw_damage_roll: int = 0
    damage_before_shield: int = 0
    shield_absorbed: int = 0
    hull_damage: int = 0


@dataclass(slots=True)
class BaseUnit(abc.ABC):
    name: str
    unit_class: UnitClass
    weapon: Weapon
    shield: Shield

    # Текущее состояние ресурсов (инициализируется максимальными значениями при создании)
    hull: int
    energy: int
    shield_hp: int

    # Флаги хода/скиллов
    skill_used: bool = False  # «скилл использован» (на бой/на ход — уточним в Arena)

    # ----- Контракт контроллера (делаем класс абстрактным без формул) -----
    @property
    @abc.abstractmethod
    def controller(self) -> str:
        raise NotImplementedError

    # ----- Базовые свойства/утилиты -----
    @property
    def hull_max(self) -> int:
        """Максимум корпуса берём из класса корабля."""
        return self.unit_class.hull_max

    @property
    def energy_max(self) -> int:
        """Максимум энергии берём из класса корабля."""
        return self.unit_class.energy_max

    @property
    def is_alive(self) -> bool:
        """Жив ли корабль (корпус > 0)."""
        return self.hull > 0

    def clamp_state(self) -> None:
        """Поджать текущие значения к допустимым границам (страховочная операция)."""
        if self.hull > self.hull_max:
            self.hull = self.hull_max
        if self.hull < 0:
            self.hull = 0

        if self.energy > self.energy_max:
            self.energy = self.energy_max
        if self.energy < 0:
            self.energy = 0

        if self.shield_hp > self.shield.capacity:
            self.shield_hp = self.shield.capacity
        if self.shield_hp < 0:
            self.shield_hp = 0

    def spend_energy(self, amount: int) -> None:
        """Списать энергию (Arena будет вызывать после применения действия/скилла)."""
        if amount < 0:
            raise ValueError("Нельзя списывать отрицательное количество энергии")
        self.energy -= amount
        if self.energy < 0:
            self.energy = 0

    def regen_energy(self, amount: int) -> None:
        """Восстановить энергию (реальная величина регена будет задана правилами боя)."""
        if amount < 0:
            raise ValueError("Нельзя восстанавливать отрицательное количество энергии")
        self.energy += amount
        if self.energy > self.energy_max:
            self.energy = self.energy_max

    def regen_shield(self) -> None:
        """
        Восстановить щит согласно предмету щита (без модификаторов класса).
        """
        self.shield_hp += self.shield.regen
        if self.shield_hp > self.shield.capacity:
            self.shield_hp = self.shield.capacity

    def mark_skill_used(self) -> None:
        self.skill_used = True

    @staticmethod
    def _clamp01(x: float) -> float:
        """Обрезает значение к диапазону [0.0, 1.0]."""
        if x < 0.0:
            return 0.0
        if x > 1.0:
            return 1.0
        return x

    def can_fire(self) -> bool:
        return self.energy > self.weapon.energy_cost

    # === Расчёт урона при попадании вынесен в отдельный метод (Template Method) ===
    def _resolve_damage_on_hit(
        self,
        *,
        target: BaseUnit,
        rng: RandomSource,
        context: AttackContext,
        notes_list: list[str],
    ) -> tuple[int, int, int, int, tuple[str, ...]]:
        """
        Считает урон при попадании и обновляет заметки.
        Возвращает: (dmg_roll, modified_damage, shield_absorbed, hull_damage, notes)
        """
        # 1) Бросок базового урона по оружию.
        dmg_roll: int = rng.randint(self.weapon.dmg_min, self.weapon.dmg_max)

        # 2) Модификаторы урона: класс юнита и контекст.
        modified_damage_f: float = (
            float(dmg_roll) * self.unit_class.attack_mod * context.damage_multiplier
        )
        modified_damage: int = max(0, int(round(modified_damage_f)))

        # 3) Итоговый "игнор щита" [0..1]
        eff_ignore: float = self._clamp01(self.weapon.shield_ignore + context.extra_shield_ignore)

        # 4) Итоговая эффективность щита цели [0..1]
        eff_shield: float = self._clamp01(
            target.shield.efficiency
            * target.unit_class.shield_mod
            * context.shield_efficiency_factor
        )

        # 5) Делим урон: часть игнорирует щит, часть идёт на щит.
        nonignored: int = int(round(modified_damage * (1.0 - eff_ignore)))
        ignored_direct: int = modified_damage - nonignored

        # 6) Щит может поглотить только долю nonignored и не больше текущего shield_hp.
        shield_absorb_potential: int = _round_half_up(nonignored * eff_shield)
        shield_absorbed: int = min(shield_absorb_potential, target.shield_hp)

        # 7) Что прошло в корпус (из неигнорируемой части) + полностью игнорирующая часть.
        hull_from_nonignored: int = nonignored - shield_absorbed
        hull_damage: int = hull_from_nonignored + ignored_direct

        # 8) Телеметрия для отладки.
        telemetry_parts: list[str] = [
            f"dmg_roll={dmg_roll} → mod={modified_damage} | ",
            f"ignore={eff_ignore:.2f} nonignored={nonignored} | ",
            f"shield_eff={eff_shield:.2f} ",
            f"absorb<=({shield_absorb_potential}) -> {shield_absorbed} | ",
            f"hull={hull_damage}",
        ]
        notes_list.append("".join(telemetry_parts))
        notes: tuple[str, ...] = tuple(notes_list)

        return dmg_roll, modified_damage, shield_absorbed, hull_damage, notes

    def basic_attack(
        self,
        target: BaseUnit,
        rng: RandomSource,
        ctx: AttackContext | None = None,
    ) -> AttackOutcome:
        context = ctx or AttackContext()

        if not self.can_fire():
            return AttackOutcome(
                hit=False,
                energy_spent=0,
                accuracy_roll=1.0,
                weapon_slug=self.weapon.slug,
                notes=("Недостаточно энергии для выстрела",),
            )

        roll: float = rng.random()
        hit: bool = roll <= self.weapon.accuracy

        notes_list: list[str] = [f"accuracy: roll={roll:.3f} vs acc={self.weapon.accuracy:.3f}"]
        if (
            context.damage_multiplier != 1.0
            or context.extra_shield_ignore != 0.0
            or context.shield_efficiency_factor != 1.0
        ):
            notes_list.append(
                f"ctx: dmgx={context.damage_multiplier:.2f}, "
                f"ignore+={context.extra_shield_ignore:.2f}, "
                f"shield_eff*={context.shield_efficiency_factor:.2f}"
            )
        notes: tuple[str, ...] = tuple(notes_list)

        if not hit:
            return AttackOutcome(
                hit=False,
                energy_spent=self.weapon.energy_cost,
                accuracy_roll=roll,
                weapon_slug=self.weapon.slug,
                notes=notes,
            )

        # Попадание: расчёт урона/щита вынесен в _resolve_damage_on_hit
        (
            dmg_roll,
            modified_damage,
            shield_absorbed,
            hull_damage,
            notes,
        ) = self._resolve_damage_on_hit(
            target=target,
            rng=rng,
            context=context,
            notes_list=notes_list,
        )

        return AttackOutcome(
            hit=True,
            energy_spent=self.weapon.energy_cost,
            accuracy_roll=roll,
            weapon_slug=self.weapon.slug,
            notes=notes,
            raw_damage_roll=dmg_roll,
            damage_before_shield=modified_damage,
            shield_absorbed=shield_absorbed,
            hull_damage=hull_damage,
        )


@dataclass(slots=True)
class PlayerUnit(BaseUnit):
    """Юнит, управляемый игроком."""

    @property
    def controller(self) -> str:
        return "player"


@dataclass(slots=True)
class AIUnit(BaseUnit):
    """Юнит, управляемый ИИ."""

    @property
    def controller(self) -> str:
        return "ai"


@overload
def create_unit(
    controller: Literal["player"],
    *,
    name: str,
    unit_class: UnitClass,
    weapon: Weapon,
    shield: Shield,
) -> PlayerUnit: ...
@overload
def create_unit(
    controller: Literal["ai"],
    *,
    name: str,
    unit_class: UnitClass,
    weapon: Weapon,
    shield: Shield,
) -> AIUnit: ...
def create_unit(
    controller: Literal["player", "ai"],
    *,
    name: str,
    unit_class: UnitClass,
    weapon: Weapon,
    shield: Shield,
) -> BaseUnit:
    hull_init: int = unit_class.hull_max
    energy_init: int = unit_class.energy_max
    shield_init: int = shield.capacity

    if controller == "player":
        return PlayerUnit(
            name=name,
            unit_class=unit_class,
            weapon=weapon,
            shield=shield,
            hull=hull_init,
            energy=energy_init,
            shield_hp=shield_init,
        )
    else:
        return AIUnit(
            name=name,
            unit_class=unit_class,
            weapon=weapon,
            shield=shield,
            hull=hull_init,
            energy=energy_init,
            shield_hp=shield_init,
        )


def create_player(
    *,
    name: str,
    unit_class: UnitClass,
    weapon: Weapon,
    shield: Shield,
) -> PlayerUnit:
    return create_unit(
        "player",
        name=name,
        unit_class=unit_class,
        weapon=weapon,
        shield=shield,
    )


def create_ai(
    *,
    name: str,
    unit_class: UnitClass,
    weapon: Weapon,
    shield: Shield,
) -> AIUnit:
    return create_unit(
        "ai",
        name=name,
        unit_class=unit_class,
        weapon=weapon,
        shield=shield,
    )
