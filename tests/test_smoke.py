from __future__ import annotations

import importlib


def test_smoke_import() -> None:
    """Дымовой тест: пакет app импортируется и имеет публичный интерфейс."""
    module = importlib.import_module("app")
    assert hasattr(module, "__all__")
