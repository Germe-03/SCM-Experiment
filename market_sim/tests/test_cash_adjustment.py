"""Cash flows outside the profit (taxes, fines, write-offs) must survive the daily cash update."""

import pytest

from market_sim.run import build_runner


def test_adjusted_cash_persists_through_following_days():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.state_actor = None  # no year-end taxes in this check
    runner.holdings = None  # no dividends either
    state = runner.start()
    runtime = runner.env.runtimes["retailer_01"]
    runtime.adjust_cash(-1_000_000.0)
    runner.run_year(state)
    assert runtime.cash == pytest.approx(runtime.initial_cash + runtime.profit - 1_000_000.0)
