from __future__ import annotations

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms
from market_sim.policies import FirmPolicy, policies_for_network
from market_sim.runner import SimulationRunner
from market_sim.strategy import FirmObservation


def _firms(network):
    return [firm for stage in network.stages for firm in stage.firms]


def test_on_order_tracks_ordered_less_received_and_never_goes_negative():
    network = load_firms()
    env = MarketEnvironment(network, horizon=12)
    env.reset()
    cumulative_ordered = {
        firm_id: runtime.on_order for firm_id, runtime in env.runtimes.items()
    }
    cumulative_received = {firm_id: 0 for firm_id in env.runtimes}

    for day in range(12):
        received = {
            firm_id: runtime.incoming_shipments[0]
            for firm_id, runtime in env.runtimes.items()
        }
        orders = {firm_id: 5 + day for firm_id in env.runtimes}
        env.step(40, orders)
        for firm_id, runtime in env.runtimes.items():
            cumulative_ordered[firm_id] += orders[firm_id]
            cumulative_received[firm_id] += received[firm_id]
            assert runtime.on_order == max(
                0, cumulative_ordered[firm_id] - cumulative_received[firm_id]
            )
            assert runtime.on_order >= 0


def test_two_year_run_has_no_runaway_inventory():
    config = load_market_config()
    network = load_firms()
    runner = SimulationRunner(
        network, config, policies_for_network(_firms(network)), seed=0
    )
    result = runner.run(years=2)

    peak_inventory = max(
        max(series["inventory"])
        for series in result.daily_series.values()
    )
    assert peak_inventory < 50 * config.demand.daily_demand_units


def test_daily_order_never_exceeds_demand_multiple_cap():
    config = load_market_config()
    firm = load_firms().firm("retailer_02")
    policy = FirmPolicy()
    strategy = policy.decide_annual(firm, None, config)

    for recent_demand in (1.0, 10.0, 259.0):
        observation = FirmObservation(
            inventory=0, backlog=100_000, pipeline_units=0, on_order=0,
            recent_demand=recent_demand, recent_sales=0, cash=firm.cash,
            day_of_year=0, quality_level=firm.quality_level,
        )
        decision = policy.decide_daily(firm, observation, strategy, config)
        assert decision.order_qty <= round(
            config.policy.max_order_demand_multiple * recent_demand
        )
