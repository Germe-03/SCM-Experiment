"""Year-end checkpoints: save a running simulation and continue it later.

A checkpoint is a pickle of the runner (network, config, policies, market
environment and all seeded RNGs) plus the cross-year ``RunState``. Pickle can
execute code while loading, so only load checkpoints this project wrote itself.
"""

from __future__ import annotations

from pathlib import Path
import pickle

from market_sim.runner import RunState, SimulationRunner

CHECKPOINT_VERSION = 6


def checkpoint_path(directory: str | Path, year: int) -> Path:
    return Path(directory) / f"year_{year:02d}.pkl"


def save_checkpoint(runner: SimulationRunner, state: RunState, path: str | Path) -> Path:
    """Write the complete simulation state at a year boundary."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": CHECKPOINT_VERSION, "runner": runner, "state": state}
    with target.open("wb") as output:
        pickle.dump(payload, output, protocol=pickle.HIGHEST_PROTOCOL)
    return target


def load_checkpoint(path: str | Path) -> tuple[SimulationRunner, RunState]:
    """Load a trusted, self-generated checkpoint (see module docstring)."""
    with Path(path).open("rb") as source:
        payload = pickle.load(source)
    if not isinstance(payload, dict) or payload.get("version") != CHECKPOINT_VERSION:
        raise ValueError(f"{path} is not a market_sim checkpoint (version {CHECKPOINT_VERSION})")
    return payload["runner"], payload["state"]


def year_end_saver(directory: str | Path):
    """Return an ``on_year_end`` callback that stores one checkpoint per year."""

    def save(runner: SimulationRunner, state: RunState) -> None:
        save_checkpoint(runner, state, checkpoint_path(directory, state.year))

    return save
