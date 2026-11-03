"""S6 capacity and cumulative financial-accounting tests."""

import pytest

from market_sim.environment import MarketEnvironment
from market_sim.models import STAGES, load_firms


def _run(days: int = 6) -> MarketEnvironment:
    network = load_firms()
    market = MarketEnvironment(
        network, horizon=days, consumer_demand_mode="attractiveness_lost",
        enforce_capacity=True,
    )
    market.reset()
    orders = {firm.id: 40 for stage in STAGES for firm in network.firms_in(stage)}
    for _ in range(days):
        market.step(30, orders)
    return market


def test_cash_identity_and_result_totals() -> None:
    market = _run()
    result = market.get_result()
    for firm_id, runtime in market.runtimes.items():
        firm = market.network.firm(firm_id)
        expected = (
            runtime.initial_cash + runtime.revenue - runtime.purchase_cost
            - runtime.cumulative_holding_cost - runtime.cumulative_backlog_cost
            - runtime.wage_cost - runtime.hiring_cost - runtime.rnd_spend
            - runtime.handling_cost - runtime.fixed_cost
        )
        assert runtime.initial_cash == firm.cash * market.config.costs.initial_cash_scale
        assert runtime.cash == pytest.approx(expected)
        assert result.firm_results[firm_id].cash == pytest.approx(expected)
    assert result.total_profit == pytest.approx(sum(r.profit for r in market.runtimes.values()))
    assert result.total_cash == pytest.approx(sum(r.cash for r in market.runtimes.values()))


def test_b2b_revenue_and_purchase_cost_are_symmetric() -> None:
    market = _run()
    # Factories buy raw materials from outside the network, not from a supplier firm.
    purchases = sum(
        market.runtimes[firm.id].purchase_cost
        for stage in STAGES[:-1] for firm in market.network.firms_in(stage)
    )
    upstream_revenue = sum(
        market.runtimes[firm.id].revenue
        for stage in STAGES[1:]
        for firm in market.network.firms_in(stage)
    )
    assert purchases == pytest.approx(upstream_revenue)


def test_capacity_flag_gates_b2b_shipping() -> None:
    network = load_firms()
    supplier = network.firm("wholesaler_01")
    supplier.capacity = 3

    def shipped(enforce: bool) -> int:
        market = MarketEnvironment(
            network, horizon=1, consumer_demand_mode="attractiveness_lost",
            enforce_capacity=enforce,
        )
        market.reset()
        runtime = market.runtimes[supplier.id]
        runtime.inventory = 100
        buyers = sorted(network.firms_in("retailer"), key=lambda firm: firm.id)[:2]
        runtime.incoming_orders[0] = {buyer.id: 20 for buyer in buyers}
        _, info = market.step(0, {})
        return sum(info["shipments"][supplier.id].values())

    assert shipped(True) <= supplier.capacity
    assert shipped(False) > supplier.capacity


def test_wages_accrue_daily() -> None:
    days = 5
    market = _run(days)
    firm = market.network.firm("retailer_01")
    assert firm.employees > 0
    assert market.runtimes[firm.id].wage_cost == pytest.approx(
        days * firm.employees * firm.wage_level / 30
        * market.config.costs.personnel_cost_scale
    )
