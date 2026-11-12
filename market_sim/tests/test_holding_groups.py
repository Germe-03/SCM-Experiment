"""Phase 40: holding groups and consolidated finances."""

from market_sim.tests._voluntary import boost_profit

import pytest

from market_sim.holding_groups import HoldingGroups
from market_sim.run import build_runner
from market_sim.runner import YearSummary


def _runner(days=10, years=1):
    runner, _ = build_runner(years, 0, days_per_year=days)
    runner.config.state.willing_share = 1.0
    state = runner.start()
    runner.continue_run(state, years)
    return runner, state


def _summaries(runner, revenue):
    return {f.id: YearSummary(revenue=revenue.get(f.id, 1.0), profit=1.0, avg_inventory=0, avg_backlog=0,
                              lost_sales=0, service_level=1, avg_sell_price=1, quality=0.5,
                              capacity_utilization=0.5, cash=0)
            for s in runner.network.stages for f in s.firms}


def test_takeover_creates_holding_and_keeps_both_firms():
    runner, state = _runner()
    env, actor = runner.env, runner.state_actor
    target = runner.network.firm("wholesaler_02")
    buyer = runner.network.firm("wholesaler_01")
    env.runtimes[target.id].consecutive_loss_years = 5
    env.runtimes[buyer.id].cash = 1e12
    runner.holdings.stakes = {}
    runner.config.state.block_share = 1.0
    runner.config.state.max_takeovers_per_stage = 1
    state.summaries.append(_summaries(runner, {}))
    boost_profit(state)  # voluntary takeovers need a clear gain
    runner.config.state.takeover_bid_probability = 1.0
    capacity = buyer.capacity

    actor.takeovers(runner, state)

    assert isinstance(runner.holding_groups, HoldingGroups)
    assert env.runtimes[buyer.id].active and env.runtimes[target.id].active
    group = runner.holding_groups.group_of(buyer.id)
    assert group is not None
    assert group.name == f"{buyer.name} Holding"
    assert group.subs == ["wholesaler_01", "wholesaler_02"]
    assert group.listing_id == "wholesaler_01"
    assert any(event["event"] == "holding_formed" for event in state.events)
    assert not any(event["event"] == "takeover" for event in state.events)
    assert buyer.capacity == capacity
    assert env.runtimes[buyer.id].cash < 1e12
    assert not any(
        event.get("firm") == target.id and event.get("event") == "takeover"
        for event in state.events
    )
    exits = getattr(state, "exits", None)
    if exits is not None:
        assert target.id not in exits


def test_second_takeover_adds_a_daughter_to_same_holding():
    runner, state = _runner()
    env, actor = runner.env, runner.state_actor
    buyer = runner.network.firm("wholesaler_01")
    target = runner.network.firm("wholesaler_02")
    env.runtimes[target.id].consecutive_loss_years = 5
    env.runtimes[buyer.id].cash = 1e12
    runner.holdings.stakes = {}
    runner.config.state.block_share = 1.0
    runner.config.state.max_takeovers_per_stage = 5
    state.summaries.append(_summaries(runner, {}))
    boost_profit(state)  # voluntary takeovers need a clear gain
    runner.config.state.takeover_bid_probability = 1.0

    actor.takeovers(runner, state)

    other = runner.network.firm("wholesaler_03")
    env.runtimes[other.id].consecutive_loss_years = 5
    actor.takeovers(runner, state)

    assert len(runner.holding_groups.groups) == 1
    group = runner.holding_groups.group_of(buyer.id)
    assert group is not None
    assert len(group.subs) >= 3
    assert other.id in group.subs


def test_acquire_refused_when_money_is_short():
    runner, state = _runner()
    buyer = runner.network.firm("wholesaler_01")
    target = runner.network.firm("wholesaler_02")
    runner.env.runtimes[buyer.id].cash = 1.0

    acquired = runner.holding_groups.acquire(runner, state, buyer, target, price=1e15, year=1, day=1)

    assert acquired is False
    assert runner.holding_groups.groups == {}


def test_sweep_moves_cash_above_reserve_to_holding_with_tax():
    runner, state = _runner()
    buyer = runner.network.firm("wholesaler_01")
    target = runner.network.firm("wholesaler_02")
    runner.env.runtimes[buyer.id].cash = 1e9
    assert runner.holding_groups.acquire(runner, state, buyer, target, price=1.0, year=1, day=1)

    state.summaries.clear()
    for _ in range(3):
        state.summaries.append(_summaries(runner, {buyer.id: 1000.0, target.id: 1000.0}))

    runner.config.holding_groups.reserve_share = 0.15
    runner.config.holding_groups.sweep_tax = 0.1
    runner.env.runtimes[buyer.id].cash = 10_000.0
    runner.env.runtimes[target.id].cash = 100.0
    group = runner.holding_groups.group_of(buyer.id)
    assert group is not None

    revenues = [
        summary[buyer.id].revenue
        for summary in state.summaries
        if buyer.id in summary
    ][-3:]
    reserve = sum(revenues) / len(revenues) * 0.15
    excess = 10_000.0 - reserve
    target_reserve = runner.holding_groups.reserve_target(state, target.id)
    assert 100.0 < target_reserve

    runner.holding_groups.year_end(runner, state)

    assert runner.env.runtimes[buyer.id].cash == pytest.approx(reserve)
    assert group.cash == pytest.approx(excess * 0.9)
    assert runner.env.runtimes[target.id].cash == 100.0
    assert runner.holding_groups.stats["sweep_tax"] == pytest.approx(excess * 0.1)
    assert any(event["event"] == "holding_sweep" for event in state.events)


def test_switch_off_keeps_old_absorption():
    runner, state = _runner()
    env, actor = runner.env, runner.state_actor
    target = runner.network.firm("wholesaler_02")
    buyer = runner.network.firm("wholesaler_01")
    env.runtimes[target.id].consecutive_loss_years = 5
    env.runtimes[buyer.id].cash = 1e12
    runner.holdings.stakes = {}
    runner.holding_groups = None
    state.summaries.append(_summaries(runner, {}))
    boost_profit(state)  # voluntary takeovers need a clear gain
    runner.config.state.takeover_bid_probability = 1.0

    actor.takeovers(runner, state)

    assert not env.runtimes[target.id].active
    assert any(event["event"] == "takeover" for event in state.events)


def test_stock_series_continues_under_holding():
    runner, state = _runner()
    buyer = runner.network.firm("wholesaler_01")
    target = runner.network.firm("wholesaler_02")
    runner.stock_market.listed.add(buyer.id)
    runner.env.runtimes[buyer.id].cash = 1000.0
    runner.env.runtimes[target.id].cash = 1000.0
    runner.env.runtimes[buyer.id].initial_cash = 1.0
    runner.env.runtimes[target.id].initial_cash = 1.0
    state.summaries = [_summaries(runner, {})]
    before = runner.stock_market.fundamental(runner, state, buyer.id)

    assert runner.holding_groups.acquire(runner, state, buyer, target, price=1.0, year=1, day=1)

    after = runner.stock_market.fundamental(runner, state, buyer.id)
    assert after > before
    assert runner.holding_groups.is_sub_only(target.id) is True
    assert runner.holding_groups.is_sub_only(buyer.id) is False
    assert runner.holding_groups.listing_alive(buyer.id)
