"""Parity proof for the independent S3 flow-mechanics port."""

from __future__ import annotations

import pytest

from market_sim.environment import MarketEnvironment
from market_sim.models import STAGES, Firm, Stage, SupplyNetwork
from supplychainbench_v2.engine.environment import Environment, EnvironmentConfig


FIRM_IDS = {stage: f"{stage}_x" for stage in STAGES}


def _firm(stage: str) -> Firm:
    index = STAGES.index(stage)
    suppliers = [FIRM_IDS[STAGES[index + 1]]] if index < len(STAGES) - 1 else []
    return Firm(
        id=FIRM_IDS[stage], name=stage.title(), stage=stage, archetype="standard",
        cash=1_000.0, inventory=12, sell_price=4.99, quality_level=0.5,
        reputation=0.5, reliability=0.5, capacity=100, employees=10,
        wage_level=25.0, productivity_per_employee=10.0, r_and_d_level=0.0,
        r_and_d_budget=0.0, supplier_priority="reliability", suppliers=suppliers,
    )


def _network() -> SupplyNetwork:
    return SupplyNetwork(stages=[Stage(name=stage, firms=[_firm(stage)]) for stage in STAGES])


def _market(horizon: int = 30) -> MarketEnvironment:
    return MarketEnvironment(
        _network(), initial_inventory=12, initial_pipeline=(5, 5),
        initial_orders=(5, 5), holding_cost=0.5, backlog_cost=1.0,
        horizon=horizon,
    )


def test_linear_market_environment_matches_reference_tick_by_tick() -> None:
    horizon = 30
    reference = Environment(EnvironmentConfig(
        horizon=horizon, initial_inventory=12, initial_pipeline=(5, 5),
        initial_orders=(5, 5), holding_cost=0.5, backlog_cost=1.0,
    ))
    market = _market(horizon)
    reference.reset()
    market.reset()
    demand = [5] * 8 + [9] * 12 + [4] * 10

    for quantity in demand:
        reference_orders = {
            stage: reference.orders_received_this_period(stage) for stage in STAGES
        }
        market_orders = {
            FIRM_IDS[stage]: market.orders_received_this_period(FIRM_IDS[stage])
            for stage in STAGES
        }
        reference_done, _ = reference.step(quantity, reference_orders)
        market_done, _ = market.step(quantity, market_orders)
        assert market_done == reference_done
        for stage in STAGES:
            expected = reference.state.get_tier(stage)
            actual = market.runtimes[FIRM_IDS[stage]]
            assert actual.inventory == expected.inventory
            assert actual.backlog == expected.backlog

    assert market.get_result().total_cost == pytest.approx(reference.get_result().total_cost)


def test_market_state_is_non_negative_and_cost_is_monotonic() -> None:
    market = _market(horizon=12)
    market.reset()
    previous_cost = 0.0

    for quantity in [3, 8, 20, 1] * 3:
        orders = {
            firm_id: market.orders_received_this_period(firm_id)
            for firm_id in market.runtimes
        }
        _, info = market.step(quantity, orders)
        assert all(runtime.inventory >= 0 and runtime.backlog >= 0 for runtime in market.runtimes.values())
        assert info["total_cost"] >= previous_cost
        previous_cost = info["total_cost"]
