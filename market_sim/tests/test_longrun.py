"""Phase 3: inflation, population, trends and the former scenarios as random events."""

import pytest

from market_sim.run import build_runner, run_simulation


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    return runner, state


def test_inflation_scales_prices_costs_and_willingness_to_pay_together():
    runner, state = _runner()
    config = runner.config
    band, fixed = config.stage_prices["retailer"].base, config.fixed_costs.base_per_day["retailer"]
    max_price = config.consumers.classes[0].max_price
    runner.long_run._inflate(runner, 1.02)
    assert config.stage_prices["retailer"].base == pytest.approx(band * 1.02)
    assert config.fixed_costs.base_per_day["retailer"] == pytest.approx(fixed * 1.02)
    assert config.consumers.classes[0].max_price == pytest.approx(max_price * 1.02)
    assert runner.long_run.price_index == pytest.approx(1.02)


def test_population_growth_raises_demand_and_ages_the_market():
    runner, state = _runner()
    mean = runner.demand.mean
    seniors = sum(c.persons for c in runner.config.consumers.classes if c.age_group == "65+")
    runner.long_run._grow_population(runner)
    assert runner.demand.mean > mean
    assert sum(c.persons for c in runner.config.consumers.classes if c.age_group == "65+") > seniors


def test_trend_switch_logs_event_and_boosts_brands_with_the_trait():
    runner, state = _runner()
    lr = runner.long_run
    lr.next_switch = 0
    state.year = 1
    lr._advance_trends(runner, state, 0.0)
    assert state.events[-1]["event"] == "trend_change"
    trait = next(t.trait for t in runner.config.long_run.trends if t.name == lr.current)
    assert runner.env.brand_book.trend_boosts[0][0] == trait
    assert runner.env.brand_book.entrant_trait == trait


def test_capacity_event_cuts_stage_capacity_only_inside_its_window():
    runner, state = _runner()
    env = runner.env
    normal = env._effective_capacity("factory_01")
    env.capacity_windows = [("factory", 0, 5, 0.5)]
    assert env._effective_capacity("factory_01") == round(normal * 0.5) or abs(
        env._effective_capacity("factory_01") - normal * 0.5) <= 1
    env.period = 6
    assert env._effective_capacity("factory_01") == normal


def test_wage_push_raises_all_wage_anchors():
    runner, state = _runner()
    event = next(t for t in runner.config.events.types if t.type == "wage_push")
    before = runner.network.firm("retailer_01").initial_wage_level
    runner._event_wage_push(event, state, 1, 10, 0.0, 0.0)
    assert runner.network.firm("retailer_01").initial_wage_level == pytest.approx(before * event.strength)


def test_disabled_long_run_keeps_price_index_flat():
    runner, _ = build_runner(2, 0, days_per_year=20)
    runner.config.long_run.enabled = False
    result = runner.continue_run(runner.start(), 2)
    assert all(k.price_index == 1.0 for k in result.system_kpis)


def test_long_run_reports_drift_in_kpis():
    result = run_simulation(years=3, seed=0, days_per_year=30)
    assert result.system_kpis[-1].price_index != 1.0
    assert result.system_kpis[-1].population_index > 1.0
