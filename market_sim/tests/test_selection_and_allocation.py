"""S4 tests for supplier choice and multi-customer fulfillment."""

from __future__ import annotations

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment, proportional_integer_allocation
from market_sim.models import STAGES, Firm, Stage, SupplyNetwork, load_firms
from market_sim.selection import select_supplier


def _firm(
    firm_id: str, *, stage: str = "wholesaler", price: float = 3.0,
    reliability: float = 0.5, quality: float = 0.5, capacity: int = 100,
    priority: str = "none", suppliers: list[str] | None = None,
) -> Firm:
    return Firm(
        id=firm_id, name=firm_id, stage=stage, archetype="standard", cash=1_000,
        inventory=20, sell_price=price, quality_level=quality, reputation=0.5,
        reliability=reliability, capacity=capacity, employees=1, wage_level=1,
        productivity_per_employee=1, r_and_d_level=0, r_and_d_budget=0,
        supplier_priority=priority, suppliers=suppliers or [],
    )


def test_supplier_selection_scores_candidates_and_is_deterministic() -> None:
    weights = load_market_config().supplier_score_weights
    downstream = _firm("buyer", stage="retailer", suppliers=["good", "weak"])
    good = _firm("good", price=2, reliability=0.9, quality=0.8, capacity=200)
    weak = _firm("weak", price=4, reliability=0.3, quality=0.4, capacity=100)

    assert select_supplier(downstream, [weak, good], weights).id == "good"
    assert select_supplier(downstream, [weak, good], weights).id == "good"


def test_price_priority_can_flip_choice() -> None:
    weights = load_market_config().supplier_score_weights
    cheap = _firm("cheap", price=2, reliability=0, quality=0, capacity=100)
    strong = _firm("strong", price=4, reliability=1, quality=1, capacity=200)
    base = _firm("base", stage="retailer", priority="none", suppliers=["cheap", "strong"])
    price_first = base.model_copy(update={"supplier_priority": "price"})

    assert select_supplier(base, [cheap, strong], weights).id == "strong"
    assert select_supplier(price_first, [cheap, strong], weights).id == "cheap"


def test_supplier_selection_ties_break_by_id() -> None:
    weights = load_market_config().supplier_score_weights
    buyer = _firm("buyer", stage="retailer", suppliers=["z_supplier", "a_supplier"])
    supplier_z = _firm("z_supplier")
    supplier_a = _firm("a_supplier")
    assert select_supplier(buyer, [supplier_z, supplier_a], weights).id == "a_supplier"


def test_proportional_allocation_is_exact_and_deterministic() -> None:
    # Both quotas have .5 remainders, so downstream id "a" receives the tie unit.
    allocation = proportional_integer_allocation(10, {"z": 30, "a": 10})
    assert allocation == {"z": 7, "a": 3}
    assert sum(allocation.values()) == 10
    assert {key: requested - allocation[key] for key, requested in {"z": 30, "a": 10}.items()} == {"z": 23, "a": 7}


def test_environment_carries_exact_backlog_per_downstream() -> None:
    retailer_z = _firm("z", stage="retailer", suppliers=["wholesaler"])
    retailer_a = _firm("a", stage="retailer", suppliers=["wholesaler"])
    wholesaler = _firm("wholesaler", suppliers=["distributor"])
    distributor = _firm("distributor", stage="distributor", suppliers=["factory"])
    factory = _firm("factory", stage="factory")
    firms = [retailer_z, retailer_a, wholesaler, distributor, factory]
    network = SupplyNetwork(stages=[
        Stage(name=stage, firms=[firm for firm in firms if firm.stage == stage])
        for stage in STAGES
    ])
    market = MarketEnvironment(network, initial_inventory=10, horizon=3)
    market.reset()
    market.step(0, {"z": 30, "a": 10})
    market.step(0, {})
    _, info = market.step(0, {})

    assert info["shipments"]["wholesaler"] == {"z": 7, "a": 3}
    assert market.runtimes["wholesaler"].backlog_by_downstream == {"a": 7, "z": 23}
    assert market.runtimes["wholesaler"].backlog == 30


def test_full_network_conserves_fulfillment_and_non_negative_state() -> None:
    market = MarketEnvironment(load_firms(), horizon=12)
    market.reset()
    previous_cost = 0.0

    for tick in range(12):
        available = {
            firm_id: runtime.inventory + runtime.incoming_shipments[0]
            for firm_id, runtime in market.runtimes.items()
        }
        orders = {firm_id: 80 + (index * 13 + tick) % 70 for index, firm_id in enumerate(sorted(market.runtimes))}
        _, info = market.step(259, orders)
        for supplier_id, allocations in info["shipments"].items():
            assert sum(allocations.values()) <= available[supplier_id]
        assert all(runtime.inventory >= 0 and runtime.backlog >= 0 for runtime in market.runtimes.values())
        assert info["total_cost"] >= previous_cost
        previous_cost = info["total_cost"]
