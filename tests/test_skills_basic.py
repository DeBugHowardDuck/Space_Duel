from __future__ import annotations

from dataclasses import dataclass

from app.skills import create_skill


@dataclass(slots=True)
class DummyUnit:
    """Простейшая заглушка, удовлетворяющая протоколу UnitLike (есть поле energy)."""

    energy: int


def test_overcharge_can_use_and_execute() -> None:
    user = DummyUnit(energy=30)
    target = DummyUnit(energy=10)
    skill = create_skill("overcharge")

    assert skill.can_use(user) is True
    result = skill.execute(user, target)

    assert result.success is True
    assert result.energy_spent == skill.energy_cost
    assert "Overcharge" in result.description


def test_overcharge_insufficient_energy() -> None:
    user = DummyUnit(energy=5)  # меньше, чем energy_cost
    target = DummyUnit(energy=10)
    skill = create_skill("overcharge")

    assert skill.can_use(user) is False
    result = skill.execute(user, target)

    assert result.success is False
    assert result.energy_spent == 0
    assert "недостаточно энергии" in result.description


def test_emp_can_use_and_execute() -> None:
    user = DummyUnit(energy=40)
    target = DummyUnit(energy=10)
    skill = create_skill("emp")

    assert skill.can_use(user) is True
    result = skill.execute(user, target)

    assert result.success is True
    assert result.energy_spent == skill.energy_cost
    assert "EMP" in result.description
