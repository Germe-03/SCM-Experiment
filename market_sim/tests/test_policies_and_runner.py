from __future__ import annotations

from market_sim.config import load_market_config
from market_sim.models import load_firms
from market_sim.policies import FirmPolicy, policies_for_network
from market_sim.runner import SimulationRunner
from market_sim.strategy import FirmObservation


def _short_config(days: int = 20):
    config = load_market_config()
    return config.model_copy(
        update={"simulation": config.simulation.model_copy(update={"days_per_year": days})}
    )


def _firms(network):
    return [firm for stage in network.stages for firm in stage.firms]


def test_archetype_strategies_are_distinct():
    config = load_market_config()
    network = load_firms()
    policy = FirmPolicy()
    premium = policy.decide_annual(network.firm("retailer_03"), None, config)
    low_cost = policy.decide_annual(network.firm("retailer_02"), None, config)
    reliable = policy.decide_annual(network.firm("retailer_09"), None, config)

    assert premium.base_price > low_cost.base_price
    assert reliable.target_safety_stock_days > low_cost.target_safety_stock_days
    assert premium.supplier_priority == "quality"
    assert low_cost.supplier_priority == "price"
    assert reliable.supplier_priority == "reliability"


def test_base_stock_daily_behavior_and_price_band():
    config = load_market_config()
    firm = load_firms().firm("retailer_02")
    policy = FirmPolicy()
    strategy = policy.decide_annual(firm, None, config)
    common = dict(
        backlog=0, recent_demand=10, recent_sales=10, cash=firm.cash,
        day_of_year=0, quality_level=firm.quality_level,
    )
    high = FirmObservation(inventory=1000, pipeline_units=100, **common)
    low = FirmObservation(inventory=0, pipeline_units=0, **common)

    high_decision = policy.decide_daily(firm, high, strategy, config)
    low_decision = policy.decide_daily(firm, low, strategy, config)
    assert high_decision.order_qty == 0
    assert low_decision.order_qty > 0
    assert strategy.min_price <= high_decision.sell_price <= strategy.max_price
    assert strategy.min_price <= low_decision.sell_price <= strategy.max_price


def test_low_cost_retailer_holds_discount_position_under_scarcity():
    config = load_market_config()
    firm = load_firms().firm("retailer_02")
    firm.sell_price = 3.98
    policy = FirmPolicy()
    strategy = policy.decide_annual(firm, None, config)
    decision = policy.decide_daily(
        firm,
        FirmObservation(
            inventory=0, backlog=10, pipeline_units=0, on_order=0,
            recent_demand=10, recent_sales=10, cash=firm.cash,
            day_of_year=0, quality_level=firm.quality_level,
        ),
        strategy,
        config,
    )

    assert decision.sell_price <= 4.0
    assert decision.sell_price < (config.stage_prices["retailer"].min + config.stage_prices["retailer"].max) / 2


def test_runner_runs_two_years_for_all_firms_and_applies_bands():
    config = _short_config()
    network = load_firms()
    runner = SimulationRunner(
        network, config, policies_for_network(_firms(network)), seed=17
    )
    result = runner.run(years=2)

    assert result.years == 2
    assert len(result.yearly_summaries) == 2
    assert all(len(year) == len(_firms(network)) for year in result.yearly_summaries)
    assert all(low <= price <= high for _, price, low, high in runner.applied_prices)
    assert all(quantity >= 0 for runtime in runner.env.runtimes.values() for quantity in runtime.order_history)


def test_runner_is_deterministic_for_fixed_seed():
    def run_once():
        config = _short_config(12)
        network = load_firms()
        result = SimulationRunner(
            network, config, policies_for_network(_firms(network)), seed=99
        ).run(years=2)
        return result.final_result.total_profit, {
            firm_id: firm.cash for firm_id, firm in result.final_result.firm_results.items()
        }

    assert run_once() == run_once()
