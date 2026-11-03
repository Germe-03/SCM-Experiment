"""Seeded start values and yearly market events."""

import pytest

from market_sim.checkpoint import load_checkpoint, year_end_saver
from market_sim.config import load_market_config
from market_sim.models import load_firms
from market_sim.run import build_runner


def _runner(seed: int, **events):
    config = load_market_config()
    if events:
        config = config.model_copy(update={"events": config.events.model_copy(update=events)})
    return build_runner(years=3, seed=seed, days_per_year=40, config=config)


def test_start_values_differ_by_seed_but_repeat_for_the_same_seed() -> None:
    def start(seed: int):
        runner, _ = _runner(seed)
        return [(f.cash, f.quality_level, f.reputation) for f in runner._firms()]

    assert start(1) == start(1)
    assert start(1) != start(2)
    originals = {f.id: f for stage in load_firms().stages for f in stage.firms}
    spread = load_market_config().start_variation
    for firm in _runner(5)[0]._firms():
        assert abs(firm.cash / originals[firm.id].cash - 1) <= spread.cash_spread + 1e-9
        assert 0.05 <= firm.quality_level <= 0.98


def test_events_are_logged_and_deterministic() -> None:
    sure = dict(heat_summer_probability=1.0, harvest_failure_probability=1.0, recall_probability=1.0)
    first, years = _runner(3, **sure)
    second, _ = _runner(3, **sure)
    one = first.continue_run(first.start(), years)
    two = second.continue_run(second.start(), years)
    assert one.events == two.events
    kinds = {event["event"] for event in one.events}
    assert kinds == {"heat_summer", "harvest_failure", "recall"}
    assert len(one.events) == 3 * years
    recall = next(e for e in one.events if e["event"] == "recall")
    assert recall["firm"] and recall["year"] == 1
    assert set(recall) == {"year", "day", "firm", "event", "details"}


def test_events_change_outcomes_between_seeds() -> None:
    sure = dict(heat_summer_probability=0.5, harvest_failure_probability=0.5, recall_probability=0.5)
    logs = []
    for seed in range(6):
        runner, years = _runner(seed, **sure)
        logs.append([(e["year"], e["event"], e["firm"]) for e in runner.continue_run(runner.start(), years).events])
    assert len({tuple(log) for log in logs}) > 1


def test_events_survive_checkpoint_and_resume(tmp_path) -> None:
    sure = dict(heat_summer_probability=1.0, harvest_failure_probability=1.0, recall_probability=1.0)
    straight, years = _runner(4, **sure)
    full = straight.continue_run(straight.start(), years)
    saved, _ = _runner(4, **sure)
    saved.continue_run(saved.start(), 1, on_year_end=year_end_saver(tmp_path))
    runner, state = load_checkpoint(tmp_path / "year_01.pkl")
    resumed = runner.continue_run(state, years)
    assert resumed.events == full.events
    assert resumed.final_result.total_profit == pytest.approx(full.final_result.total_profit)
