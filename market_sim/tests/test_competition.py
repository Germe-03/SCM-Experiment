"""P2 tests for persistent supplier competition."""

from __future__ import annotations

from market_sim.config import load_market_config
from market_sim.models import Firm, load_firms
from market_sim.policies import policies_for_network
from market_sim.runner import SimulationRunner
from market_sim.selection import split_order


def _firm(firm_id: str, **changes) -> Firm:
    values = dict(
        id=firm_id, name=firm_id, stage="wholesaler", archetype="standard",
        cash=1_000, inventory=20, sell_price=3.0, quality_level=0.5,
        reputation=0.5, reliability=0.5, capacity=100, employees=1,
        wage_level=1, productivity_per_employee=1, r_and_d_level=0,
        r_and_d_budget=0, supplier_priority="none", suppliers=[],
    )
    values.update(changes)
    return Firm(**values)


def test_split_order_is_exact_deterministic_and_favors_better_supplier() -> None:
    weights = load_market_config().supplier_score_weights
    buyer = _firm("buyer", stage="retailer", suppliers=["good", "weak"])
    good = _firm("good", sell_price=2, reliability=0.9, quality_level=0.8)
    weak = _firm("weak", sell_price=4, reliability=0.3, quality_level=0.4)

    first = split_order(buyer, [weak, good], 101, weights)
    assert first == split_order(buyer, [weak, good], 101, weights)
    assert first["good"] > first["weak"]
    assert all(isinstance(value, int) for value in first.values())
    assert sum(first.values()) == 101
    assert split_order(buyer, [good], 101, weights) == {"good": 101}


def test_reputation_increases_supplier_share() -> None:
    weights = load_market_config().supplier_score_weights
    buyer = _firm("buyer", stage="retailer", suppliers=["a", "b"])
    a = _firm("a")
    b = _firm("b")
    tied = split_order(buyer, [a, b], 1_000, weights)
    improved = split_order(
        buyer, [a.model_copy(update={"reputation": 1.0}), b], 1_000, weights
    )
    assert improved["a"] > tied["a"]


def test_real_run_routes_orders_to_both_suppliers_at_each_upstream_tier() -> None:
    config = load_market_config()
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    runner = SimulationRunner(network, config, policies_for_network(firms), seed=0)
    runner.run(2)

    total_orders = {
        firm_id: sum(runtime.orders_received_history)
        for firm_id, runtime in runner.env.runtimes.items()
    }
    for tier in ("wholesaler", "distributor", "factory"):
        # Firms that entered at the last year end have not received orders yet.
        suppliers = [firm for firm in network.firms_in(tier) if "_e" not in firm.id and "_s" not in firm.id]
        assert all(total_orders[firm.id] > 0 for firm in suppliers)
