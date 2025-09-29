from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import ClassVar, Protocol


class UnitLike(Protocol):
    """Мини-протокол, чтобы типизировать взаимодействие."""

    energy: int


@dataclass(frozen=True, slots=True)
class SkillResult:
    """Результат применения скилла."""

    success: bool
    energy_spent: int
    description: str


class ShipSkill(abc.ABC):
    """Template Method: execute() — проверка, затем _perform() — конкретная реализация."""

    name: ClassVar[str] = "base-skill"
    energy_cost: ClassVar[int] = 0

    def can_use(self, user: UnitLike) -> bool:
        """Проверка достаточности энергии у пользователя скилла."""
        return user.energy >= self.energy_cost

    def execute(self, user: UnitLike, target: UnitLike) -> SkillResult:
        """
        Шаблонный метод:
        1) Проверяем can_use().
        2) Делаем _perform().
        3) Возвращаем SkillResult.
        """
        if not self.can_use(user):
            return SkillResult(False, 0, f"{self.name}: недостаточно энергии")
        description: str = self._perform(user, target)
        return SkillResult(True, self.energy_cost, description)

    @abc.abstractmethod
    def _perform(self, user: UnitLike, target: UnitLike) -> str:
        raise NotImplementedError


_SKILL_REGISTRY: dict[str, type[ShipSkill]] = {}


def register_skill(name: str, cls: type[ShipSkill]) -> None:
    """Регистрирует класс скилла по имени (ключ фабрики)."""
    if name in _SKILL_REGISTRY:
        raise KeyError(f"Skill '{name}' уже зарегистрирован")
    _SKILL_REGISTRY[name] = cls


def create_skill(name: str) -> ShipSkill:
    """Создаёт экземпляр скилла по имени."""
    try:
        skill_cls = _SKILL_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Skill '{name}' не найден") from exc
    return skill_cls()


def skill_registered(name: str) -> bool:
    """Проверяет, зарегистрирован ли скилл."""
    return name in _SKILL_REGISTRY


class Overcharge(ShipSkill):
    """Скилл: кратковременное усиление следующего выстрела."""

    name: ClassVar[str] = "Overcharge"
    energy_cost: ClassVar[int] = 20

    def _perform(self, user: UnitLike, target: UnitLike) -> str:
        return "Overcharge: следующий выстрел усилен"


class EMP(ShipSkill):
    """Скилл: ЭМИ-импульс; временно подавляет щиты цели."""

    name: ClassVar[str] = "EMP"
    energy_cost: ClassVar[int] = 25

    def _perform(self, user: UnitLike, target: UnitLike) -> str:
        return "EMP: щиты цели временно подавлены"


register_skill("overcharge", Overcharge)
register_skill("emp", EMP)
