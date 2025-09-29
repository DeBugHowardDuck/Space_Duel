from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Literal

StatsResult = Literal["win", "loss", "draw"]


@dataclass(slots=True)
class SessionStats:
    fights: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def winrate(self) -> float:
        return (self.wins / self.fights) if self.fights else 0.0


def load_from(raw: Mapping[str, Any] | None) -> SessionStats:
    if not raw:
        return SessionStats()
    return SessionStats(
        fights=int(raw.get("fights", 0)),
        wins=int(raw.get("wins", 0)),
        losses=int(raw.get("losses", 0)),
        draws=int(raw.get("draws", 0)),
    )


def dump(stats: SessionStats) -> dict[str, Any]:
    data = asdict(stats)
    data["winrate"] = round(stats.winrate * 100, 1)
    return data


def bump(stats: SessionStats, result: StatsResult | str) -> SessionStats:
    kind = (result or "").strip().lower()
    if kind not in {"win", "loss", "draw"}:
        raise ValueError(f"Unknown result kind: {result!r}")

    s = SessionStats(stats.fights, stats.wins, stats.losses, stats.draws)

    s.fights += 1
    if kind == "win":
        s.wins += 1
    elif kind == "loss":
        s.losses += 1
    else:  # "draw"
        s.draws += 1

    return s
