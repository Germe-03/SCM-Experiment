"""S7 opt-in workforce and delayed R&D behaviour."""

import pytest

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def _environment(*, workforce=False, rnd=False, config=None):
    network = load_firms()
    env = MarketEnvironment(
        network, config=config, enable_workforce=workforce, enable_rnd=rnd,
        enforce_capacity=True, initial_inventory=10_000, horizon=20,
    )
    env.reset()
    return env


def test_overtime_raises_capacity_and_wage_cost() -> None:
    env = _environment(workforce=True)
    firm = env.network.firms_in("factory")[0]
    firm.capacity = 10
    firm.employees = 1
    firm.productivity_per_employee = 1
    firm.overtime_level = 0.5
    overtime_capacity = env._effective_capacity(firm.id)
    env.step(0, {})
    overtime_wage = env.runtimes[firm.id].wage_cost

    firm.overtime_level = 0.0
    baseline_capacity = env._effective_capacity(firm.id)
    expected_base_wage = firm.employees * firm.wage_level / env.config.workforce.days_per_month
    assert overtime_capacity > baseline_capacity
    assert overtime_wage > expected_base_wage


def test_wages_reduce_and_overtime_increases_turnover() -> None:
    env = _environment(workforce=True)
    low, high = env.network.firms_in("retailer")[:2]
    low.wage_level, low.overtime_level = 3_000, 0.0
    high.wage_level, high.overtime_level = 7_000, 0.0
    env.step(0, {})
    assert env.runtimes[high.id].turnover_rate < env.runtimes[low.id].turnover_rate
    old_rate = env.runtimes[low.id].turnover_rate
    low.overtime_level = 1.0
    env.step(0, {})
    assert env.runtimes[low.id].turnover_rate > old_rate


def test_turnover_cost_and_churn_reduce_throughput() -> None:
    cfg = load_market_config()
    high_churn = cfg.model_copy(update={
        "workforce": cfg.workforce.model_copy(update={"base_annual_turnover": 18.25}),
        # Raw materials scale with output; drop them so cash only reflects churn cost.
        "commodities": cfg.commodities.model_copy(update={"components": {}}),
    })
    with_churn = _environment(workforce=True, config=high_churn)
    without = _environment(workforce=False, config=high_churn)
    firm_a = with_churn.network.firms_in("factory")[0]
    firm_b = without.network.firms_in("factory")[0]
    for firm in (firm_a, firm_b):
        firm.capacity = 100
        firm.employees = 1
        firm.productivity_per_employee = 1
        firm.overtime_level = 0
    with_churn.runtimes[firm_a.id].employees = 1
    without.runtimes[firm_b.id].employees = 1
    with_churn.step(0, {firm_a.id: 1_000})
    without.step(0, {firm_b.id: 1_000})
    runtime = with_churn.runtimes[firm_a.id]
    assert runtime.hiring_cost > 0
    assert runtime.cash < without.runtimes[firm_b.id].cash
    assert with_churn._effective_capacity(firm_a.id) < without._effective_capacity(firm_b.id)
    assert runtime.incoming_shipments[-1] < without.runtimes[firm_b.id].incoming_shipments[-1]


def test_rnd_is_delayed_capped_and_then_decays() -> None:
    cfg = load_market_config()
    cfg = cfg.model_copy(update={
        "rnd": cfg.rnd.model_copy(update={
            "lag_days": 3, "effect_per_chf": 0.01,
            "daily_quality_decay": 0.001, "quality_cap": 0.6,
        })
    })
    env = _environment(rnd=True, config=cfg)
    firm = env.network.firms_in("factory")[0]
    firm.quality_level = 0.5
    firm.r_and_d_budget = 365
    env.runtimes[firm.id].quality_level = 0.5
    for expected in (0.499, 0.498):
        env.step(0, {})
        assert env.runtimes[firm.id].quality_level == pytest.approx(expected)
    env.step(0, {})
    assert env.runtimes[firm.id].quality_level > 0.498
    for _ in range(20):
        env.step(0, {})
    assert env.runtimes[firm.id].quality_level <= cfg.rnd.quality_cap
    firm.r_and_d_budget = 0
    # Drain already-scheduled effects, then observe depreciation.
    for _ in range(cfg.rnd.lag_days):
        env.step(0, {})
    quality = env.runtimes[firm.id].quality_level
    env.step(0, {})
    assert env.runtimes[firm.id].quality_level < quality


def test_enabled_cash_identity_includes_hiring_and_rnd() -> None:
    env = _environment(workforce=True, rnd=True)
    for _ in range(4):
        env.step(20, {})
    for runtime in env.runtimes.values():
        assert runtime.cash == pytest.approx(
            runtime.initial_cash + runtime.revenue - runtime.purchase_cost
            - runtime.cumulative_holding_cost - runtime.cumulative_backlog_cost
            - runtime.wage_cost - runtime.hiring_cost - runtime.rnd_spend
            - runtime.handling_cost - runtime.fixed_cost - runtime.interest_cost
        )
