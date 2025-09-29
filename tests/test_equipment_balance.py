from app.equipment import (
    SHIELD_REGISTRY,
    WEAPON_REGISTRY,
    get_shield,
    get_weapon,
    load_equipment_from_json,
)


def test_equipment_items_registered():
    load_equipment_from_json("equipment.json")
    # оружие
    assert "laser_mk1" in WEAPON_REGISTRY
    assert "railgun_mk1" in WEAPON_REGISTRY
    w = get_weapon("laser_mk1")
    assert 0.0 <= w.accuracy <= 1.0
    assert 0.0 <= w.shield_ignore <= 1.0
    # щиты
    for slug in [
        "shield_basic",
        "shield_heavy",
        "shield_light",
        "shield_medium",
        "shield_capacitor",
    ]:
        assert slug in SHIELD_REGISTRY
    s = get_shield("shield_medium")
    assert 0.0 < s.efficiency <= 1.0
