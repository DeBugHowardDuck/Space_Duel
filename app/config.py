from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Config:
    SECRET_KEY: str = "dev-secret"
    DEBUG: bool = False
    TESTING: bool = False

    ARENA_RNG_SEED: str | None = None
    AI_SKILL_CHANCE: str | None = None


def make_config_from_env() -> Config:
    cfg = Config()
    cfg.SECRET_KEY = os.getenv("SECRET_KEY", cfg.SECRET_KEY)
    cfg.DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    cfg.ARENA_RNG_SEED = os.getenv("ARENA_RNG_SEED")
    cfg.AI_SKILL_CHANCE = os.getenv("AI_SKILL_CHANCE")

    return cfg
