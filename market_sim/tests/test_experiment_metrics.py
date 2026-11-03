"""Experiment indicators in SystemKPIs and the events.csv log."""

import csv
from types import SimpleNamespace

import pytest

from market_sim.config import load_market_config
from market_sim.run import EVENT_FIELDS, build_runner, run_simulation, write_outputs
from market_sim.runner import YearSummary


@pytest.fixture(scope="module")
def short_run():
    return run_simulation(years=3, seed=0)


def test_new_kpis_are_filled_and_plausible(short_run) -> None:
    kpis = short_run.system_kpis
    for item in kpis:
        for stage in ("retailer", "wholesaler", "distributor", "factory"):
            assert -1.0 < getattr(item, f"margin_{stage}") < 1.0
            assert 0.0 < getattr(item, f"utilization_{stage}") <= 1.0
        assert item.retailer_price_spread > 0
        assert 0 <= item.firms_with_loss <= 22
    assert kpis[0].market_share_movement == 0.0
    assert kpis[1].market_share_movement > 0.0
    assert all(item.market_entries == 0 for item in kpis)


def test_bankruptcies_are_counted_and_logged(tmp_path) -> None:
    config = load_market_config()
    config = config.model_copy(update={"bankruptcy": config.bankruptcy.model_copy(update={
        "cash_threshold": 1e15, "min_firms_per_stage": 0, "max_exits_per_stage_per_year": 0,
    })})
    result = run_simulation(years=2, days_per_year=5, seed=0, config=config)
    exits = [e for e in result.events if e["event"] == "bankruptcy"]
    assert len(exits) == len(result.exits) == 22
    assert result.system_kpis[0].bankruptcies == 22
    assert result.system_kpis[1].bankruptcies == 0
    assert all(e["year"] == 1 and e["day"] == 5 for e in exits)

    write_outputs(result, tmp_path)
    with (tmp_path / "events.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
    assert reader.fieldnames == EVENT_FIELDS
    assert len(rows) == len(result.events)


def test_price_supplier_and_capacity_events() -> None:
    runner, _ = build_runner(years=1, seed=0, days_per_year=20)
    runner.env.reset()
    firm = runner.network.firm("retailer_01")

    def summary(price: float) -> YearSummary:
        return YearSummary(
            revenue=1.0, profit=1.0, avg_inventory=0.0, avg_backlog=0.0, lost_sales=0,
            service_level=1.0, avg_sell_price=price, quality=0.7,
            capacity_utilization=0.5, cash=1.0,
        )

    state = SimpleNamespace(events=[], main_supplier={firm.id: "wholesaler_01"})
    firms = runner._firms()
    summaries = {f.id: summary(5.0) for f in firms}
    summaries[firm.id] = summary(5.6)
    previous = {firm.id: summary(5.0)}
    utilization = {f.id: [0.5] * 20 for f in firms}
    utilization[firm.id] = [0.5] * 3 + [0.97] * 8 + [0.5] * 9
    shipped = {f.id: {} for f in firms}
    shipped[firm.id] = {"wholesaler_01": 10, "wholesaler_02": 40}

    runner._log_year_events(state, 2, summaries, previous, utilization, shipped)

    by_kind = {event["event"]: event for event in state.events}
    assert set(by_kind) == {"price_increase", "supplier_switch", "capacity_limit"}
    assert all(event["firm"] == firm.id and event["year"] == 2 for event in state.events)
    assert by_kind["capacity_limit"]["day"] == 4
    assert "wholesaler_02" in by_kind["supplier_switch"]["details"]
    # A move of exactly 5 % or less is not logged.
    state.events.clear()
    summaries[firm.id] = summary(5.2)
    runner._log_year_events(state, 2, summaries, previous, {f.id: [0.5] * 20 for f in firms}, shipped)
    assert not [e for e in state.events if e["event"].startswith("price")]
