"""Phase 41: holding group cover, sales, takeovers and dissolution."""

import pytest

from market_sim.run import build_runner
from market_sim.runner import YearSummary


def _runner(days=10, years=1):
    runner, _ = build_runner(years, 0, days_per_year=days)
    runner.config.state.willing_share = 1.0
    state = runner.start()
    runner.continue_run(state, years)
    return runner, state


def _summaries(runner, revenue, profit=1.0):
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


def _set_three_year_summaries(runner, state, revenue, profit=1.0):
    state.summaries.clear()
    for _ in range(3):
        state.summaries.append(_summaries(runner, revenue, profit))


def _form_group(runner, state, subsidiary_ids):
    buyer = runner.network.firm("wholesaler_01")
    runner.env.runtimes[buyer.id].cash = 1e9
    for subsidiary_id in subsidiary_ids:
        target = runner.network.firm(subsidiary_id)
        assert runner.holding_groups.acquire(
            runner, state, buyer, target, price=1.0, year=1, day=1
        )
    group = runner.holding_groups.group_of(buyer.id)
    assert group is not None
    return group


def _set_revenue_and_cash(runner, state, firm_ids, cash):
    revenues = {firm_id: 1000.0 for firm_id in firm_ids}
    _set_three_year_summaries(runner, state, revenues)
    for firm_id in firm_ids:
        runner.env.runtimes[firm_id].cash = cash


def test_cover_tops_sub_up_to_ten_percent_when_holding_has_cash():
    runner, state = _runner()
    group = _form_group(runner, state, ["wholesaler_02", "wholesaler_03"])
    firm_ids = ["wholesaler_01", "wholesaler_02", "wholesaler_03"]
    _set_revenue_and_cash(runner, state, firm_ids, 1000.0)
    runner.config.holding_groups.min_reserve_share = 0.1
    runner.config.holding_groups.cover_cash_share = 0.5
    runner.env.runtimes["wholesaler_02"].cash = 0.0
    group.cash = 10_000.0

    runner.holding_groups.after_sweep(runner, state, 2)

    assert runner.env.runtimes["wholesaler_02"].cash == pytest.approx(100.0)
    assert group.cash == pytest.approx(9_900.0)
    assert any(event["event"] == "holding_cover" for event in state.events)
    assert runner.holding_groups.stats["covered"] > 0


def test_no_cover_below_half_of_revenue():
    runner, state = _runner()
    group = _form_group(runner, state, ["wholesaler_02"])
    firm_ids = ["wholesaler_01", "wholesaler_02"]
    _set_revenue_and_cash(runner, state, firm_ids, 1000.0)
    runner.config.holding_groups.min_reserve_share = 0.1
    runner.config.holding_groups.cover_cash_share = 0.5
    runner.env.runtimes["wholesaler_02"].cash = 0.0
    group.cash = 100.0

    runner.holding_groups.after_sweep(runner, state, 2)

    assert runner.env.runtimes["wholesaler_02"].cash == 0.0
    assert group.cash == 100.0
    assert any(event["event"] == "holding_no_cover" for event in state.events)
    assert not any(event["event"] == "holding_cover" for event in state.events)


def test_holding_sells_chronically_losing_daughter():
    runner, state = _runner()
    group = _form_group(runner, state, ["wholesaler_02", "wholesaler_03"])
    firm_ids = ["wholesaler_01", "wholesaler_02", "wholesaler_03"]
    _set_revenue_and_cash(runner, state, firm_ids, 1000.0)
    runner.config.holding_groups.sale_revenue_factor = 0.2
    runner.env.runtimes["wholesaler_03"].consecutive_loss_years = 5

    runner.holding_groups.after_sweep(runner, state, 2)

    assert "wholesaler_03" not in group.subs
    assert runner.holding_groups.group_of("wholesaler_03") is None
    assert group.cash == pytest.approx(0.2 * 1000.0)
    assert any(event["event"] == "holding_sold" for event in state.events)
    assert runner.env.runtimes["wholesaler_03"].active

    runner_two, state_two = _runner()
    group_two = _form_group(runner_two, state_two, ["wholesaler_02"])
    _set_revenue_and_cash(
        runner_two, state_two, ["wholesaler_01", "wholesaler_02"], 1000.0
    )
    runner_two.env.runtimes["wholesaler_02"].consecutive_loss_years = 5

    runner_two.holding_groups.after_sweep(runner_two, state_two, 2)

    assert "wholesaler_02" in group_two.subs
    assert not any(event["event"] == "holding_sold" for event in state_two.events)


def test_dissolves_when_only_one_daughter_left():
    runner, state = _runner()
    group = _form_group(runner, state, ["wholesaler_02"])
    _set_revenue_and_cash(
        runner, state, ["wholesaler_01", "wholesaler_02"], 1000.0
    )
    group.cash = 5000.0
    runner.env.runtimes["wholesaler_02"].active = False

    runner.holding_groups.after_sweep(runner, state, 2)

    assert group.dissolved_year == 2
    assert group.successor == "wholesaler_01"
    assert runner.env.runtimes["wholesaler_01"].cash == pytest.approx(6000.0)
    assert runner.holding_groups.group_of("wholesaler_01") is None
    assert not runner.holding_groups.listing_alive("wholesaler_01")
    assert runner.holding_groups.listing_owner["wholesaler_01"] == "wholesaler_01"
    assert runner.holding_groups.owner_of_listing("wholesaler_01") == "wholesaler_01"
    assert any(event["event"] == "holding_dissolved" for event in state.events)

    runner.stock_market.fundamental(runner, state, "wholesaler_01")


def _prepare_distressed_holding_takeover(runner, state, block_share):
    group = _form_group(runner, state, ["wholesaler_02"])
    firm_ids = ["wholesaler_01", "wholesaler_02", "wholesaler_03"]
    revenues = {firm_id: 1000.0 for firm_id in firm_ids}
    _set_three_year_summaries(runner, state, revenues)
    runner.config.holding_groups.holding_takeovers = True
    runner.config.holding_groups.cover_cash_share = 0.5
    runner.config.state.block_share = block_share
    runner.env.runtimes["wholesaler_01"].cash = -1e9
    runner.env.runtimes["wholesaler_02"].cash = -1e9
    runner.env.runtimes["wholesaler_03"].cash = 1e12
    for firm in runner._firms():
        if firm.id not in firm_ids and firm.stage == runner.network.firm("wholesaler_01").stage:
            runner.env.runtimes[firm.id].cash = 1e6
    return group


def test_distressed_holding_is_bought_with_daughters():
    runner, state = _runner()
    old_group = _prepare_distressed_holding_takeover(runner, state, block_share=1.0)

    runner.holding_groups.after_sweep(runner, state, 2)

    new_group = runner.holding_groups.group_of("wholesaler_03")
    assert new_group is not None
    assert set(new_group.subs) == {
        "wholesaler_01",
        "wholesaler_02",
        "wholesaler_03",
    }
    assert old_group.dissolved_year == 2
    assert old_group.successor == new_group.id
    assert any(event["event"] == "holding_takeover" for event in state.events)
    assert "wholesaler_01" not in runner.holding_groups.listing_group


def test_antitrust_blocks_holding_takeover():
    runner, state = _runner()
    old_group = _prepare_distressed_holding_takeover(runner, state, block_share=0.0)

    runner.holding_groups.after_sweep(runner, state, 2)

    assert old_group.dissolved_year is None
    assert runner.holding_groups.group_of("wholesaler_01") is old_group
    assert any(event["event"] == "takeover_blocked" for event in state.events)
