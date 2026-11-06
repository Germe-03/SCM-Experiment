"""Raw materials, fixed costs and the relative bankruptcy rule."""

import pytest

from market_sim.checkpoint import load_checkpoint, year_end_saver
from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms
from market_sim.policies import policies_for_network
from market_sim.run import build_runner
from market_sim.runner import SimulationRunner


def _env(config=None, days: int = 70) -> MarketEnvironment:
    env = MarketEnvironment(
        load_firms(), config=config, horizon=days, enforce_capacity=True, enable_workforce=True, seed=3,
    )
    env.reset()
    return env


def _orders(env: MarketEnvironment, quantity: int = 30) -> dict[str, int]:
    return {f.id: quantity for s in env.network.stages for f in s.firms}


def test_factory_pays_raw_materials_per_produced_unit() -> None:
    config = load_market_config()
    flat = config.model_copy(update={"commodities": config.commodities.model_copy(
        update={"index_volatility": 0.0})})
    # Wine is only pressed at harvest; this test covers the daily production path.
    flat.categories.enabled = False
    env = _env(flat)
    unit_cost = sum(config.commodities.components.values())
    assert env.material_cost_per_unit() == pytest.approx(unit_cost)
    env.step(0, _orders(env, 20))
    # The two breweries can produce 20 units a day; the small Phase-4 producers cannot.
    for factory_id in ("factory_01", "factory_02"):
        assert env.runtimes[factory_id].purchase_cost == pytest.approx(20 * unit_cost)
    # Downstream firms only pay their suppliers, never raw materials.
    assert env.runtimes["retailer_01"].purchase_cost == 0


def test_commodity_index_moves_and_is_seeded() -> None:
    config = load_market_config()
    config = config.model_copy(update={"commodities": config.commodities.model_copy(
        update={"market_enabled": False})})
    first, second = _env(config), _env(config)
    for env in (first, second):
        for _ in range(65):
            env.step(0, _orders(env, 0))
    assert first.commodity_log_index == second.commodity_log_index
    assert any(value != 0 for value in first.commodity_log_index.values())
    assert first.material_cost_per_unit() != pytest.approx(
        sum(config.commodities.components.values())
    )


def test_fixed_costs_grow_with_capacity() -> None:
    env = _env()
    small, large = sorted(env.network.firms_in("retailer"), key=lambda f: f.capacity)[::len(env.network.firms_in("retailer")) - 1]
    env.step(0, {})
    assert env.runtimes[small.id].fixed_cost > 0
    assert env.runtimes[large.id].fixed_cost > env.runtimes[small.id].fixed_cost


def test_relative_bankruptcy_rule_scales_with_starting_capital() -> None:
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    config = load_market_config()
    config.bank.enabled = False
    config = config.model_copy(update={"bankruptcy": config.bankruptcy.model_copy(update={
        "min_firms_per_stage": 0, "max_exits_per_stage_per_year": 0,
        "negative_cash_years": 0, "cash_floor_fraction": 1.0,
    })})
    runner = SimulationRunner(network, config, policies_for_network(firms), seed=0)
    runner.env.reset()
    small, large = "retailer_06", "factory_02"
    for firm_id in (small, large):
        runtime = runner.env.runtimes[firm_id]
        runtime.cash = -0.9 * runtime.initial_cash
    runner.env.runtimes[small].cash = -1.1 * runner.env.runtimes[small].initial_cash
    runner._apply_bankruptcy(1)
    assert small in runner.exits and large not in runner.exits


def test_negative_cash_years_and_stage_minimum() -> None:
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    config = load_market_config()
    config.bank.enabled = False
    config = config.model_copy(update={"bankruptcy": config.bankruptcy.model_copy(update={
        "cash_floor_fraction": None, "negative_cash_years": 2,
        "min_firms_per_stage": 1, "max_exits_per_stage_per_year": 0,
    })})
    runner = SimulationRunner(network, config, policies_for_network(firms), seed=0)
    runner.env.reset()
    for runtime in runner.env.runtimes.values():
        runtime.cash = -1.0
    runner._apply_bankruptcy(1)
    assert runner.exits == {}  # one negative year is not enough
    runner._apply_bankruptcy(2)
    # The stage minimum is protected; among producers also the last one of each category.
    for stage, expected in (("retailer", 1), ("factory", 3)):
        active = [f for f in network.firms_in(stage) if runner.env.runtimes[f.id].active]
        assert len(active) == expected


def test_commodity_state_survives_checkpoint_resume(tmp_path) -> None:
    straight, years = build_runner(years=2, seed=1, days_per_year=40)
    full = straight.continue_run(straight.start(), years)
    saved, years = build_runner(years=2, seed=1, days_per_year=40)
    saved.continue_run(saved.start(), 1, on_year_end=year_end_saver(tmp_path))
    runner, state = load_checkpoint(tmp_path / "year_01.pkl")
    resumed = runner.continue_run(state, 2)
    assert resumed.final_result.total_profit == pytest.approx(full.final_result.total_profit)
    assert runner.env.commodity_log_index == straight.env.commodity_log_index
