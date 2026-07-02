"""Tests for the central market configuration."""

from __future__ import annotations

import pytest

from market_sim.config import MarketConfig, load_market_config


@pytest.fixture(scope="module")
def market_config() -> MarketConfig:
    return load_market_config()


def test_default_config_contains_swiss_market_values(
    market_config: MarketConfig,
) -> None:
    assert market_config.unit_scale.real_units_per_sim_unit == 10_000
    assert market_config.demand.annual_demand_units == 94_400
    assert market_config.demand.daily_demand_units == 259
    assert market_config.price.base == 4.99
    assert market_config.total_simulation_days == 3_650
    assert market_config.logistics.default_lead_time_days == 2
    assert market_config.costs.holding_cost_per_unit == 27.0
    assert market_config.costs.backlog_cost_per_unit == 250.0
    assert market_config.costs.handling_cost_per_unit == 8_200.0
    assert market_config.policy.supplier_priority_boost == 50.0


def test_weight_groups_sum_to_one(market_config: MarketConfig) -> None:
    attractiveness = market_config.demand_attractiveness_weights
    supplier = market_config.supplier_score_weights
    assert sum(segment.share for segment in market_config.demand.segments) == pytest.approx(1.0)
    assert all(
        segment.weights.price + segment.weights.quality
        + segment.weights.reputation + segment.weights.availability
        == pytest.approx(1.0)
        for segment in market_config.demand.segments
    )

    assert (
        attractiveness.price
        + attractiveness.quality
        + attractiveness.reputation
        + attractiveness.availability
    ) == pytest.approx(1.0)
    assert (
        supplier.price
        + supplier.reliability
        + supplier.quality
        + supplier.reputation
        + supplier.lead_time
        + supplier.capacity
    ) == pytest.approx(1.0)


def test_price_ordering_invariant(market_config: MarketConfig) -> None:
    assert market_config.price.min <= market_config.price.base <= market_config.price.max
