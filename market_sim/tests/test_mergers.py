"""Phase 43: voluntary merger formation and integration."""

import pytest

from market_sim.run import build_runner
from market_sim.runner import YearSummary


def _runner(days=10, years=1):
    runner, _ = build_runner(years, 0, days_per_year=days)
    runner.config.state.willing_share = 1.0
    runner.config.mergers.enabled = False
    state = runner.start()
    runner.continue_run(state, years)
    runner.config.mergers.enabled = True
    return runner, state


def _summaries(runner, revenue: dict, profit: float | dict = 1.0):
    return {
        firm.id: YearSummary(
            revenue=revenue.get(firm.id, 1.0),
            profit=profit.get(firm.id, 1.0) if isinstance(profit, dict) else profit,
            avg_inventory=0,
            avg_backlog=0,
            lost_sales=0,
            service_level=1,
            avg_sell_price=1,
            quality=0.5,
            capacity_utilization=0.5,
            cash=0,
        )
        for stage in runner.network.stages
        for firm in stage.firms
    }


def _set_summaries(runner, state, revenue, profit=1.0):
    state.summaries.clear()
    state.summaries.append(_summaries(runner, revenue, profit))


def _prepare_pair(runner, state, first_id, second_id, first_revenue=1000.0, second_revenue=800.0):
    revenues = {firm.id: 0.0 for firm in runner._firms()}
    revenues[first_id] = first_revenue
    revenues[second_id] = second_revenue
    _set_summaries(runner, state, revenues)

    cfg = runner.config.mergers
    cfg.enabled = True
    cfg.max_per_year = 1
    cfg.base_probability = 1.0
    cfg.weak_multiplier = 1.0
    cfg.min_share_gain = 0.0
    cfg.max_market_share = 1.0
    cfg.min_size_ratio = 0.01

    state.events.clear()


def test_merger_creates_new_firm_and_closes_parents():
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "wholesaler_02")
    runner.config.mergers.double_name_ratio = 0.6

    big = runner.network.firm("wholesaler_01")
    small = runner.network.firm("wholesaler_02")
    big_runtime = runner.env.runtimes[big.id]
    small_runtime = runner.env.runtimes[small.id]
    cash_before = big_runtime.cash + small_runtime.cash
    capacity_before = big.capacity + small.capacity
    employees_before = big.employees + small.employees

    runner.mergers.year_end(runner, state)

    assert len(runner.mergers.log) == 1
    row = runner.mergers.log[0]
    new_id = row["new"]
    assert new_id.startswith("wholesaler_f")
    assert runner.env.runtimes[new_id].active
    assert not big_runtime.active
    assert not small_runtime.active
    assert any(event["event"] == "merger_formed" for event in state.events)
    merger_events = [event for event in state.events if event["event"] == "merger"]
    assert len(merger_events) == 2
    assert {event["firm"] for event in merger_events} == {big.id, small.id}
    assert row["parents"] == ["wholesaler_01", "wholesaler_02"]
    assert runner.env.runtimes[new_id].cash == pytest.approx(cash_before)

    new_firm = next(firm for firm in runner._firms() if firm.id == new_id)
    assert new_firm.capacity == capacity_before
    assert new_firm.employees == employees_before
    assert runner.env.merger_efficiency[new_id] == pytest.approx(
        1 - runner.config.mergers.efficiency_loss
    )
    assert runner.env.merger_fixed_factor[new_id] == pytest.approx(
        1 + runner.config.mergers.integration_cost_share
    )
    assert new_firm.name == f"{big.name} & {small.name}"
    assert {big.id, small.id}.issubset(
        {event["firm"] for event in merger_events}
    )


def test_smaller_firm_under_one_third_does_not_merge():
    runner, state = _runner()
    _prepare_pair(
        runner, state, "wholesaler_01", "wholesaler_02", 1000.0, 100.0
    )
    runner.config.mergers.min_size_ratio = 1 / 3

    runner.mergers.year_end(runner, state)

    assert not runner.mergers.log
    assert not any(event["event"] == "merger_formed" for event in state.events)


def test_state_blocks_merger_over_forty_percent():
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "wholesaler_02")
    runner.config.mergers.max_market_share = 0.3

    runner.mergers.year_end(runner, state)

    assert any(event["event"] == "merger_blocked" for event in state.events)
    assert runner.env.runtimes["wholesaler_01"].active
    assert runner.env.runtimes["wholesaler_02"].active
    assert runner.mergers.stats["mergers_blocked"] >= 1


def test_integration_year_then_fixed_cost_saving():
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "wholesaler_02")
    runner.mergers.year_end(runner, state)
    new_id = runner.mergers.log[0]["new"]
    saving = runner.mergers.new_firms[new_id]["saving"]

    state.year += 1
    runner.config.mergers.enabled = False
    runner.mergers.year_end(runner, state)

    assert new_id not in runner.env.merger_efficiency
    assert runner.env.merger_fixed_factor[new_id] == pytest.approx(1 - saving)
    assert runner.config.mergers.fixed_saving_min <= saving
    assert saving <= runner.config.mergers.fixed_saving_max


def test_merger_off_by_config():
    runner, state = _runner()
    runner.config.mergers.enabled = False
    state.events.clear()
    runtime_ids = set(runner.env.runtimes)

    runner.mergers.year_end(runner, state)

    assert not state.events
    assert set(runner.env.runtimes) == runtime_ids


def test_merger_transfers_stock_brands_and_research():
    runner, state = _runner()
    factories = runner.network.firms_in("factory")
    by_category = {}
    for firm in factories:
        by_category.setdefault(firm.category, []).append(firm)
    pair = next(
        (firms[:2] for firms in by_category.values() if len(firms) >= 2),
        None,
    )
    if pair is None:
        pytest.skip("No two factories share a category")

    first, second = pair
    _prepare_pair(runner, state, first.id, second.id)
    brands = set(runner.env.brand_book.brands_of(first.id))
    brands.update(runner.env.brand_book.brands_of(second.id))
    assert brands

    first_runtime = runner.env.runtimes[first.id]
    second_runtime = runner.env.runtimes[second.id]
    first_runtime.stock = {"merger-stock-a": 3}
    second_runtime.stock = {"merger-stock-b": 5}
    first_runtime.inventory = 7
    second_runtime.inventory = 11

    runner.mergers.year_end(runner, state)

    new_id = runner.mergers.log[0]["new"]
    new_runtime = runner.env.runtimes[new_id]
    assert all(runner.env.brand_book.brands[brand].owner == new_id for brand in brands)
    assert new_runtime.inventory == 18
    assert new_runtime.stock == {"merger-stock-a": 3, "merger-stock-b": 5}


def test_adjacent_stage_merger_allowed():
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "distributor_01", 1000.0, 900.0)

    runner.mergers.year_end(runner, state)

    assert len(runner.mergers.log) == 1
    new_id = runner.mergers.log[0]["new"]
    assert new_id.startswith("wholesaler_f")
    new_firm = next(firm for firm in runner._firms() if firm.id == new_id)
    assert new_firm.stage == "wholesaler"


def test_run_continues_after_merger(monkeypatch):
    runner, state = _runner()
    runner.config.mergers.enabled = True
    runner.config.mergers.max_per_year = 1
    runner.config.mergers.base_probability = 1.0
    runner.config.mergers.weak_multiplier = 1.0
    runner.config.mergers.min_share_gain = 0.0
    runner.config.mergers.max_market_share = 1.0
    runner.config.mergers.min_size_ratio = 0.01
    monkeypatch.setattr(runner.mergers.rng, "random", lambda: 0.0)
    state.events.clear()

    runner.mergers.year_end(runner, state)
    formed = [event for event in state.events if event["event"] == "merger_formed"]
    if not formed:
        pytest.skip("No compatible positive-revenue firms to merge")
    new_id = formed[0]["firm"]

    runner.config.mergers.enabled = False
    runner.continue_run(state, 1)

    assert new_id in state.summaries[-1]


def test_holding_subsidiary_does_not_merge(monkeypatch):
    """Phase 44: firms inside a holding stay out of mergers."""
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "wholesaler_02")
    groups = runner.holding_groups
    monkeypatch.setattr(groups, "group_of", lambda firm_id: object() if firm_id == "wholesaler_01" else None)

    runner.mergers.year_end(runner, state)

    assert all("wholesaler_01" not in row["parents"] for row in runner.mergers.log)
    assert runner.env.runtimes["wholesaler_01"].active


def test_merger_moves_commodity_stock():
    """Phase 44: the raw-material stock goes to the merged firm."""
    runner, state = _runner()
    _prepare_pair(runner, state, "wholesaler_01", "wholesaler_02")
    env = runner.env
    env.commodity_stock["wholesaler_01"] = {"malz": 10.0}
    env.commodity_stock["wholesaler_02"] = {"malz": 5.0, "hopfen": 2.0}

    runner.mergers.year_end(runner, state)

    new_id = runner.mergers.log[0]["new"]
    assert env.commodity_stock[new_id] == {"malz": 15.0, "hopfen": 2.0}
    assert "wholesaler_01" not in env.commodity_stock
    assert "wholesaler_02" not in env.commodity_stock


def test_transfer_commodity_stock_for_takeover():
    runner, _ = _runner()
    env = runner.env
    env.commodity_stock["a"] = {"malz": 4.0}
    env.commodity_stock["b"] = {"malz": 1.0}
    env.transfer_commodity_stock("a", "b")
    env.transfer_commodity_stock("missing", "b")
    assert env.commodity_stock == {"b": {"malz": 5.0}} or env.commodity_stock["b"] == {"malz": 5.0}
    assert "a" not in env.commodity_stock
