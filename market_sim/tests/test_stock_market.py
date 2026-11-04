"""Stock exchange: listing from year X, daily prices, event shocks, rate effect, chain-linked index."""

import types

import pytest

from market_sim.run import build_runner


def test_nothing_trades_before_tradable_year():
    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.tradable_from_year = 3
    state = runner.start()
    sm = runner.stock_market

    sm.daily(runner, state, 2, 0, 0)

    assert sm.listed == set()
    assert sm.daily_rows == []

    sm.daily(runner, state, 3, 0, 1)

    active = {fid for fid, rt in runner.env.runtimes.items() if rt.active}
    assert sm.listed == active
    assert sum(event["event"] == "exchange_opened" for event in state.events) == 1


def test_prices_positive_and_deterministic():
    rows = []
    for _ in range(2):
        runner, _ = build_runner(days_per_year=4)
        runner.config.stock_market.tradable_from_year = 1
        state = runner.start()
        sm = runner.stock_market

        for day in range(30):
            sm.daily(runner, state, 1, day, day)

        rows.append(sm.daily_rows)

    assert rows[0] == rows[1]
    listed = {fid for fid in rows[0][0] if fid not in {"global_day", "year", "day", "index"}}
    assert all(row[fid] > 0 for row in rows[0] for fid in listed)


def test_event_shock_moves_price():
    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.tradable_from_year = 1
    state = runner.start()
    sm = runner.stock_market

    sm.daily(runner, state, 1, 0, 0)
    fid = sorted(sm.listed)[0]
    before = sm.sentiment[fid]
    state.events.append({"year": 1, "day": 1, "firm": fid,
                         "event": "poisoning", "details": ""})
    sm.cfg.volatility = 0.0

    sm.daily(runner, state, 1, 1, 1)

    assert sm.sentiment[fid] < before - 0.4


def test_higher_policy_rate_lowers_fundamental():
    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.tradable_from_year = 1
    state = runner.start()
    sm = runner.stock_market
    assert runner.config.central_bank.enabled is True

    fid = next(fid for fid, rt in runner.env.runtimes.items() if rt.active)
    state.summaries = [{fid: types.SimpleNamespace(profit=1_000_000.0)}]

    runner.env.central_bank.policy_rate = 0.0
    low_rate_value = sm.fundamental(runner, state, fid)
    runner.env.central_bank.policy_rate = 0.05
    high_rate_value = sm.fundamental(runner, state, fid)

    assert low_rate_value > high_rate_value


def test_delisting_keeps_index_continuous():
    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.tradable_from_year = 1
    state = runner.start()
    sm = runner.stock_market

    sm.daily(runner, state, 1, 0, 0)
    sm.cfg.volatility = 0.0
    sm.cfg.reversion = 0.0
    sm.daily(runner, state, 1, 1, 1)
    idx = sm.index
    fid = sorted(sm.listed)[0]
    runner.env.runtimes[fid].active = False

    sm.daily(runner, state, 1, 2, 2)

    assert fid not in sm.listed
    assert sm.index == pytest.approx(idx)
    assert any(event["event"] == "delisted" and event["firm"] == fid
               for event in state.events)


def test_disabled_market_does_nothing():
    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.tradable_from_year = 1
    state = runner.start()
    sm = runner.stock_market
    sm.cfg.enabled = False

    sm.daily(runner, state, 1, 0, 0)

    assert sm.daily_rows == []
    assert sm.listed == set()
