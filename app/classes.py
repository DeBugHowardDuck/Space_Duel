from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnitClass:
    """Параметры класса корабля модификаторы и пределы."""

    name: str
    hull_max: int
    energy_max: int
    shield_mod: float
    attack_mod: float


CLASS_REGISTRY: dict[str, UnitClass] = {}


def register_unit_class(slug: str, unit_class: UnitClass) -> None:
    """Регистрирует класс корабля."""
    if slug in CLASS_REGISTRY:
        raise KeyError(f"UnitClass '{slug}' уже зарегистрирован")
    CLASS_REGISTRY[slug] = unit_class


def get_unit_class(slug: str) -> UnitClass:
    """Возвращает класс корабля или кидает KeyError."""
    try:
        return CLASS_REGISTRY[slug]
    except KeyError as exc:
        raise KeyError(f"UnitClass '{slug}' не найден") from exc
