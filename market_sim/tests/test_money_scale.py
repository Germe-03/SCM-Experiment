"""P4a real-CHF valuation tests for trades expressed in simulation units."""

import pytest

from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def test_b2b_shipment_books_scaled_symmetric_trade_value() -> None:
    network = load_firms()
    market = MarketEnvironment(
        network, horizon=1, consumer_demand_mode="attractiveness_lost"
    )
    market.reset()
    supplier = network.firm("wholesaler_01")
    buyer_id = "retailer_01"
    quantity = 3
    market.runtimes[supplier.id].inventory = quantity
    market.runtimes[supplier.id].incoming_orders[0] = {buyer_id: quantity}

    market.step(0, {})

    expected = (
        quantity * supplier.sell_price
        * market.config.unit_scale.real_units_per_sim_unit
    )
    assert market.runtimes[supplier.id].revenue == pytest.approx(expected)
    assert market.runtimes[buyer_id].purchase_cost == pytest.approx(expected)


def test_consumer_sale_books_scaled_retail_revenue() -> None:
    network = load_firms()
    market = MarketEnvironment(
        network, horizon=1, consumer_demand_mode="attractiveness_lost"
    )
    market.reset()
    retailer = network.firm("retailer_01")
    quantity = 2
    for candidate in network.firms_in("retailer"):
        market.runtimes[candidate.id].inventory = 0
    market.runtimes[retailer.id].inventory = quantity

    _, info = market.step(quantity, {})

    sold = info["consumer_units_sold"][retailer.id]
    expected = (
        sold * retailer.sell_price
        * market.config.unit_scale.real_units_per_sim_unit
    )
    assert sold == quantity
    assert market.runtimes[retailer.id].revenue == pytest.approx(expected)


def test_cash_identity_holds_over_scaled_run() -> None:
    network = load_firms()
    market = MarketEnvironment(
        network, horizon=4, consumer_demand_mode="attractiveness_lost",
        enforce_capacity=True, enable_workforce=True, enable_rnd=True,
    )
    market.reset()
    orders = {firm.id: 20 for stage in network.stages for firm in stage.firms}

    for _ in range(4):
        market.step(20, orders)

    for runtime in market.runtimes.values():
        assert runtime.cash == pytest.approx(
            runtime.initial_cash + runtime.revenue - runtime.purchase_cost
            - runtime.cumulative_holding_cost - runtime.cumulative_backlog_cost
            - runtime.wage_cost - runtime.hiring_cost - runtime.rnd_spend
            - runtime.handling_cost - runtime.fixed_cost - runtime.interest_cost
        )
