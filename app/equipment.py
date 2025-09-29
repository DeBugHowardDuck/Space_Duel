from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal

from marshmallow import Schema, ValidationError
from marshmallow_dataclass import class_schema

# ====== Датаклассы экипировки ======


@dataclass(frozen=True, slots=True)
class Weapon:
    """
    Оружие: лазер/рельсотрон. Поля подобраны под будущие формулы урона/энергии/игнора щита.
    Значения вероятностей указываются в диапазоне [0.0, 1.0].
    """

    slug: str  # ключ (строчными), уникален в реестре
    name: str  # отображаемое имя
    kind: Literal["laser", "railgun"]  # noqa: UP037
    dmg_min: int  # минимальный базовый урон
    dmg_max: int  # максимальный базовый урон
    energy_cost: int  # стоимость выстрела по энергии
    shield_ignore: float  # доля урона, проходящая мимо щита (0..1)
    accuracy: float  # вероятность попадания (0..1)


@dataclass(frozen=True, slots=True)
class Shield:
    """
    Щит как предмет экипировки.
    capacity: «прочность щита» (батарея/запас очков щита).
    efficiency: коэффициент поглощения входящего урона щитом (0..1).
    regen: восстановление щита в начале хода.
    """

    slug: str  # ключ (строчными), уникален в реестре
    name: str  # отображаемое имя
    capacity: int  # максимальный запас очков щита (HP щита)
    efficiency: float  # какая доля входящего урона поглощается щитом (0..1)
    regen: int  # восстановление щита за ход


# ====== Схемы marshmallow для (де)сериализации ======

WeaponSchema: type[Schema] = class_schema(Weapon)
ShieldSchema: type[Schema] = class_schema(Shield)


# ====== Реестры (Factory/Registry) ======

WEAPON_REGISTRY: dict[str, Weapon] = {}
SHIELD_REGISTRY: dict[str, Shield] = {}


def _ensure_slug(slug: str) -> str:
    """Валидация и нормализация слага (должен быть нижним регистром, без пробелов)."""
    normalized = slug.strip().lower()
    if normalized != slug or " " in normalized:
        raise ValueError(f"Некорректный slug '{slug}': используйте нижний регистр без пробелов")
    return normalized


def register_weapon(weapon: Weapon) -> None:
    """Регистрирует оружие; защищает от дубликатов."""
    key = _ensure_slug(weapon.slug)
    if key in WEAPON_REGISTRY:
        raise KeyError(f"Weapon '{key}' уже зарегистрирован")
    WEAPON_REGISTRY[key] = weapon


def register_shield(shield: Shield) -> None:
    """Регистрирует щит; защищает от дубликатов."""
    key = _ensure_slug(shield.slug)
    if key in SHIELD_REGISTRY:
        raise KeyError(f"Shield '{key}' уже зарегистрирован")
    SHIELD_REGISTRY[key] = shield


def get_weapon(slug: str) -> Weapon:
    """Возвращает оружие по слагу или бросает KeyError с понятным текстом."""
    key = slug.lower()
    try:
        return WEAPON_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Weapon '{slug}' не найден") from exc


def get_shield(slug: str) -> Shield:
    """Возвращает щит по слагу или бросает KeyError с понятным текстом."""
    key = slug.lower()
    try:
        return SHIELD_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Shield '{slug}' не найден") from exc


# ====== Загрузка из JSON ======


def load_equipment_from_json(
    src: IO[str] | str | Path,
) -> tuple[dict[str, Weapon], dict[str, Shield]]:
    """
    Загружает оборудование из JSON-источника и возвращает (weapons, shields).
    """
    # 1) Получаем текст JSON
    if isinstance(src, (str | Path)):
        text = Path(src).read_text(encoding="utf-8")
    else:
        text = src.read()

    # Парсим JSON
    try:
        payload_raw: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"equipment.json: некорректный JSON: {exc}") from exc
    WEAPON_REGISTRY.clear()
    SHIELD_REGISTRY.clear()

    # Нормолизация формата.
    if isinstance(payload_raw, dict):
        payload: dict[str, object] = payload_raw
    elif isinstance(payload_raw, list):
        weapons_raw = [
            it
            for it in payload_raw
            if isinstance(it, Mapping) and ("kind" in it or "dmg_min" in it)
        ]
        shields_raw = [
            it
            for it in payload_raw
            if isinstance(it, Mapping) and ("capacity" in it or "efficiency" in it)
        ]
        payload = {"weapons": weapons_raw, "shields": shields_raw}
    else:
        raise ValueError("equipment.json: ожидался объект или список объектов")

    raw_weapons: list[dict[str, object]] = _as_list(payload.get("weapons", []))
    raw_shields: list[dict[str, object]] = _as_list(payload.get("shields", []))

    w_schema = WeaponSchema()
    s_schema = ShieldSchema()

    weapons: dict[str, Weapon] = {}
    shields: dict[str, Shield] = {}

    for item in raw_weapons:
        try:
            weapon = w_schema.load(item)
        except ValidationError as exc:
            raise ValueError(f"Ошибка в weapon: {exc.messages}") from exc
        register_weapon(weapon)
        weapons[weapon.slug] = weapon

    for item in raw_shields:
        try:
            shield = s_schema.load(item)
        except ValidationError as exc:
            raise ValueError(f"Ошибка в shield: {exc.messages}") from exc
        register_shield(shield)
        shields[shield.slug] = shield

    return weapons, shields


def _as_list(value: object) -> list[dict[str, object]]:
    """Гарантирует, что значение — список словарей."""
    if isinstance(value, Sequence) and all(isinstance(x, Mapping) for x in value):
        return [dict(x) for x in value]
    raise ValueError("Ожидался список объектов: [...]")
