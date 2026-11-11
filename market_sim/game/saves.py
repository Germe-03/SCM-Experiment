from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path
from typing import Callable

from market_sim.game.player import PlayerSettings
from market_sim.game.session import GameSession, RoundSnapshot


@dataclass
class SaveGame:
    """Enthält einen Spielstand."""

    seed: int
    years: int | None
    days_per_year: int | None
    branch: str
    name: str
    region: str | None
    category: str | None
    rounds: list[dict] = field(default_factory=list)
    choices: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    saved_at: str = ""
    label: str = ""


def write_save(save: SaveGame, path: Path) -> Path:
    """Schreibt einen Spielstand als JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(save), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_save(path: Path) -> SaveGame:
    """Liest einen Spielstand aus JSON."""

    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {item.name for item in fields(SaveGame)}
    return SaveGame(**{key: value for key, value in data.items() if key in allowed})


def list_saves(directory: Path) -> list[dict]:
    """Listet gültige Spielstände eines Ordners."""

    if not directory.exists():
        return []

    saves = []
    for path in directory.glob("*.json"):
        try:
            save = read_save(path)
            saves.append({
                "name": path.stem,
                "label": save.label,
                "saved_at": save.saved_at,
                "firm": save.name,
            })
        except Exception:
            continue

    return sorted(saves, key=lambda item: item["saved_at"], reverse=True)


def replay(
    save: SaveGame,
    on_snapshot: Callable[[RoundSnapshot], None] | None = None,
) -> tuple[GameSession, RoundSnapshot]:
    """Spielt gespeicherte Runden erneut ab."""

    session = GameSession(save.seed, save.years, save.days_per_year)
    session.found(save.branch, save.name, save.region, save.category)
    snap = session.start()
    if on_snapshot:
        on_snapshot(snap)

    for index, round_settings in enumerate(save.rounds):
        round_choices = save.choices[index] if index < len(save.choices) else None
        round_orders = save.orders[index] if index < len(save.orders) else None
        snap = session.end_round(PlayerSettings(**round_settings), round_choices or None, round_orders or None)
        if on_snapshot:
            on_snapshot(snap)

    return session, snap
