"""Interest tiers, inflation and stage reporting."""

import pytest

from market_sim.run import build_runner


@pytest.mark.parametrize("cash,revenue,index", [(20e6, 0, 1), (50e6, 0, 1), (100e6, 0, 1), (100e6, 180e6, 1), (100e6, 0, 2), (-100e6, 0, 1), (0, 0, 1)])
def test_interest_tiers(cash, revenue, index):
    runner, _ = build_runner(1, 0, days_per_year=10)
    env = runner.env
    env.reset()
    rt = env.runtimes["retailer_01"]
    rt.cash, rt.last_year_revenue, env.price_index = cash, revenue, index
    cfg = runner.config.bank
    threshold = max(50e6 * index, revenue * 0.5)
    negative = max(0, cash - threshold) * 0.0075 / 365
    expected = (negative - min(cash, threshold) * cfg.deposit_rate / 365 if cash >= 0 else
                -cash * min(cfg.max_rate, cfg.base_rate + cfg.leverage_premium) / 365)
    env._apply_interest(rt)
    assert rt.cash == pytest.approx(cash - expected)
    assert rt.interest_cost == pytest.approx(expected)
    assert rt.negative_interest_cost == pytest.approx(negative)


def test_disabled_and_inflation_index():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    runner.long_run._inflate(runner, 1.1)
    assert runner.env.price_index == pytest.approx(1.1)
    rt = runner.env.runtimes["retailer_01"]
    rt.cash = 100e6
    runner.config.bank.negative_interest_enabled = False
    runner.env._apply_interest(rt)
    assert rt.negative_interest_cost == 0
    assert rt.interest_cost == pytest.approx(-100e6 * 0.005 / 365)


def test_stage_kpis_are_annual_not_cumulative():
    runner, _ = build_runner(2, 0, days_per_year=10)
    result = runner.run(2)
    for index, kpi in enumerate(result.system_kpis):
        for stage in ("retailer", "wholesaler", "distributor", "factory"):
            expected = sum(result.financial_breakdown[f.id][index]["negative_interest_cost"] for f in runner.network.firms_in(stage))
            assert getattr(kpi, f"negative_interest_{stage}") == pytest.approx(expected)
