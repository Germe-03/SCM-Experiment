"""P4b fix: market-size dynamics and firm-exit coverage."""

from copy import deepcopy

import pytest

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms
from market_sim.policies import policies_for_network
from market_sim.runner import ConsumerDemandGenerator, SimulationRunner
from market_sim.selection import select_supplier, split_order


def test_seasonality_has_expected_peak_trough_and_stays_positive():
    generator = ConsumerDemandGenerator(
        1000, 0, seasonal_amplitude=0.25, seasonal_phase_days=90,
    )
    factors = [generator.seasonal_factor(day) for day in range(365)]
    assert min(factors) > 0
    assert max(factors) / min(factors) == pytest.approx(1.25 / 0.75, rel=0.01)
    assert factors.index(max(factors)) == pytest.approx(181, abs=1)




def test_inactive_firm_is_frozen_and_excluded_from_market_operations():
    config = load_market_config()
    network = load_firms()
    env = MarketEnvironment(
        network, config=config,
        enforce_capacity=True, enable_workforce=True, enable_rnd=True,
    )
    env.reset()
    retailer = sorted(network.firms_in("retailer"), key=lambda firm: firm.id)[0]
    runtime = env.runtimes[retailer.id]
    runtime.cash = -config.bankruptcy.cash_floor_fraction * runtime.initial_cash - 1
    runtime.active = False
    before = (
        runtime.cash, runtime.revenue, runtime.purchase_cost, runtime.wage_cost,
        runtime.hiring_cost, runtime.rnd_spend, len(runtime.order_history),
        len(runtime.shipment_history), runtime.cumulative_consumer_units_sold,
    )
    _, info = env.step(500, {firm.id: 100 for stage in network.stages for firm in stage.firms})
    after = (
        runtime.cash, runtime.revenue, runtime.purchase_cost, runtime.wage_cost,
        runtime.hiring_cost, runtime.rnd_spend, len(runtime.order_history),
        len(runtime.shipment_history), runtime.cumulative_consumer_units_sold,
    )
    assert after == before
    assert retailer.id not in info["consumer_demand_shares"]
    assert retailer.id not in info["split_orders"]

    downstream = deepcopy(retailer)
    suppliers = network.suppliers_of(retailer.id)
    active_ids: set[str] = set()
    assert split_order(
        downstream, suppliers, 100, config.supplier_score_weights,
        active_firm_ids=active_ids,
    ) == {}
    assert select_supplier(
        downstream, suppliers, config.supplier_score_weights,
        active_firm_ids=active_ids,
    ) is None


def test_bankruptcy_disabled_does_not_imply_exit():
    config = load_market_config().model_copy(
        update={"bankruptcy": load_market_config().bankruptcy.model_copy(update={"enabled": False})}
    )
    network = load_firms()
    env = MarketEnvironment(network, config=config)
    env.reset()
    runtime = next(iter(env.runtimes.values()))
    runtime.cash = -config.bankruptcy.cash_floor_fraction * runtime.initial_cash - 1
    env.step(0, {})
    assert runtime.active


def test_runner_applies_year_end_bankruptcy_and_honors_disabled_switch():
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    base = load_market_config()
    base.bank.enabled = False
    base.mergers.enabled = False  # a voluntary merger would also close firms
    enabled = base.model_copy(update={
        "bankruptcy": base.bankruptcy.model_copy(update={
            "enabled": True, "cash_threshold": 10**30, "min_years_before_exit": 1,
            "min_firms_per_stage": 0, "max_exits_per_stage_per_year": 0,
        })
    })
    runner = SimulationRunner(network, enabled, policies_for_network(firms), seed=0)
    runner.run(1)
    assert not any(runtime.active for runtime in runner.env.runtimes.values())

    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    disabled = enabled.model_copy(update={
        "bankruptcy": enabled.bankruptcy.model_copy(update={"enabled": False})
    })
    runner = SimulationRunner(network, disabled, policies_for_network(firms), seed=0)
    runner.run(1)
    assert all(runtime.active for runtime in runner.env.runtimes.values())
