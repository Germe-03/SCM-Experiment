"""Tests for firm models and the supply network."""

from __future__ import annotations

import pytest

from market_sim.models import STAGES, Firm, Stage, SupplyNetwork, load_firms


@pytest.fixture(scope="module")
def network() -> SupplyNetwork:
    return load_firms()


def test_default_network_has_competitive_funnel(network: SupplyNetwork) -> None:
    counts = {stage: len(network.firms_in(stage)) for stage in STAGES}
    assert counts == {"retailer": 10, "wholesaler": 6, "distributor": 4, "factory": 2}
    assert sum(counts.values()) == 22
    assert all(2 <= count <= 10 for count in counts.values())


def test_supplier_topology_resolves_to_firms(network: SupplyNetwork) -> None:
    assert all(not firm.suppliers for firm in network.firms_in("factory"))

    for retailer in network.firms_in("retailer"):
        suppliers = network.suppliers_of(retailer.id)
        assert all(isinstance(supplier, Firm) for supplier in suppliers)
        assert all(supplier.stage == "wholesaler" for supplier in suppliers)

    for stage in STAGES[:-1]:
        expected_stage = network.upstream_stage(stage)
        expected_ids = {firm.id for firm in network.firms_in(expected_stage)}
        for firm in network.firms_in(stage):
            assert set(firm.suppliers) == expected_ids
            assert all(
                supplier.stage == expected_stage
                for supplier in network.suppliers_of(firm.id)
            )


def test_archetypes_are_loaded(network: SupplyNetwork) -> None:
    assert network.firm("retailer_01").archetype == "standard"
    assert network.firm("retailer_02").archetype == "low_cost"
    assert network.firm("factory_01").archetype == "premium"


def test_wrong_stage_supplier_raises_value_error() -> None:
    network = load_firms()
    retailer = network.firm("retailer_01").model_copy(
        update={"suppliers": ["factory_01"]}
    )
    stages = [
        Stage(
            name=stage,
            firms=[
                retailer if firm.id == retailer.id else firm
                for firm in network.firms_in(stage)
            ],
        )
        for stage in STAGES
    ]

    with pytest.raises(ValueError, match="must be in stage 'wholesaler'"):
        SupplyNetwork(stages=stages)
