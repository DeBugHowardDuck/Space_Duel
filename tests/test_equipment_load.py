from __future__ import annotations

import io
from collections.abc import Iterable

import pytest

from app.equipment import (
    SHIELD_REGISTRY,
    WEAPON_REGISTRY,
    get_shield,
    get_weapon,
    load_equipment_from_json,
)


@pytest.fixture(autouse=True)
def _clear_registries() -> Iterable[None]:
    """Перед каждым тестом очищаем реестры, чтобы избежать конфликтов по slug."""
    WEAPON_REGISTRY.clear()
    SHIELD_REGISTRY.clear()
    yield
    WEAPON_REGISTRY.clear()
    SHIELD_REGISTRY.clear()


def test_load_from_stringio_success() -> None:
    """Успешная загрузка 2 пушек и 2 щитов; инварианты выполнены."""
    data = io.StringIO(
        """
        {
          "weapons": [
            {"slug":"laser_mk1","name":"Laser Mk I","kind":"laser","dmg_min":8,
            "dmg_max":14,"energy_cost":10,"shield_ignore":0.10,"accuracy":0.85},
            {"slug":"railgun_mk1","name":"Railgun Mk I","kind":"railgun",
            "dmg_min":12,"dmg_max":20,"energy_cost":14,"shield_ignore":0.25,"accuracy":0.75}
          ],
          "shields": [
            {"slug":"shield_basic","name":"Basic Shield","capacity":30,"efficiency":0.6,"regen":3},
            {"slug":"shield_heavy","name":"Heavy Shield","capacity":45,"efficiency":0.7,"regen":2}
          ]
        }
        """.strip()
    )
    weapons, shields = load_equipment_from_json(data)

    assert set(weapons) == {"laser_mk1", "railgun_mk1"}
    assert set(shields) == {"shield_basic", "shield_heavy"}

    # Инварианты оружия
    for w in weapons.values():
        assert w.dmg_min <= w.dmg_max
        assert 0.0 <= w.shield_ignore <= 1.0
        assert 0.0 <= w.accuracy <= 1.0
        assert w.energy_cost >= 0

    # Инварианты щитов
    for s in shields.values():
        assert s.capacity >= 0
        assert 0.0 <= s.efficiency <= 1.0
        assert s.regen >= 0

    # Проверка доступа через get_*
    assert get_weapon("laser_mk1").name == "Laser Mk I"
    assert get_shield("shield_heavy").capacity == 45


def test_duplicate_weapon_slug_raises_key_error() -> None:
    """Дублирующийся slug оружия должен приводить к KeyError при регистрации."""
    data = io.StringIO(
        """
        {
          "weapons": [
            {"slug":"laser_mk1","name":"A","kind":"laser","dmg_min":1,"dmg_max":2,"energy_cost":1,"shield_ignore":0.1,"accuracy":0.9},
            {"slug":"laser_mk1","name":"B","kind":"laser","dmg_min":2,"dmg_max":3,"energy_cost":2,"shield_ignore":0.2,"accuracy":0.8}
          ],
          "shields": []
        }
        """.strip()
    )
    with pytest.raises(KeyError):
        load_equipment_from_json(data)


def test_wrong_structure_raises_value_error() -> None:
    """Неверная структура (не список объектов) должна приводить к ValueError."""
    data = io.StringIO(
        """
        {
          "weapons": {"slug":"x"},
          "shields": []
        }
        """.strip()
    )
    with pytest.raises(ValueError):
        load_equipment_from_json(data)
