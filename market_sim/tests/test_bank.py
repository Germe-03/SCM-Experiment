"""Daily interest and credit cancellation."""

import pytest

from market_sim.run import build_runner


@pytest.mark.parametrize("cash", [-1000.0, 1000.0])
def test_daily_interest(cash):
    runner, _ = build_runner()
    runner.start()
    runtime = runner.env.runtimes["retailer_01"]
    runtime.cash = cash
    runtime.last_year_revenue = 2000
    runtime.consecutive_loss_years = 2
    cfg = runner.config.bank
    expected = (1000 * min(cfg.max_rate, cfg.base_rate + 2 * cfg.risk_premium_per_loss_year
                          + cfg.leverage_premium * 0.5) / 365 if cash < 0
                else -1000 * cfg.deposit_rate / 365)
    runner.env._apply_interest(runtime)
    assert runtime.interest_cost == pytest.approx(expected)
    assert runtime.cash == pytest.approx(cash - expected)


def test_credit_limit_cancels_loan():
    runner, _ = build_runner()
    runner.start()
    runtime = runner.env.runtimes["retailer_01"]
    runtime.credit_limit = 100
    runtime.cash = -101
    events = []
    runner._apply_bankruptcy(5, events)
    assert not runtime.active
    assert "bank cancelled credit" in events[0]["details"]


def test_disabled_bank_and_rate_cap():
    runner, _ = build_runner()
    runner.start()
    runtime = runner.env.runtimes["retailer_01"]
    runtime.cash = -1000
    runtime.consecutive_loss_years = 100
    runner.env._apply_interest(runtime)
    assert runtime.interest_cost == pytest.approx(1000 * runner.config.bank.max_rate / 365)
    before = runtime.interest_cost
    runner.config.bank.enabled = False
    runner.env._apply_interest(runtime)
    assert runtime.interest_cost == before


def test_year_end_limit_and_financial_reporting():
    runner, _ = build_runner(days_per_year=3)
    runner.config.market_entry.enabled = False
    state = runner.start()
    runner.run_year(state)
    cfg = runner.config.bank
    for firm in runner._firms():
        runtime = runner.env.runtimes[firm.id]
        report = state.annual_reports[-1][firm.id]
        assert runtime.credit_limit == pytest.approx(max(cfg.credit_limit_min,
            cfg.credit_limit_revenue_fraction * report.revenue
            + cfg.credit_limit_initial_cash_fraction * runtime.initial_cash))
        assert report.interest_cost == state.financial_breakdown[firm.id][-1]["interest_cost"]
        assert runtime.cash == pytest.approx(runtime.initial_cash + runtime.profit)
