"""Tests for firm models and the supply network."""

from __future__ import annotations

import pytest

from market_sim.models import STAGES, Firm, Stage, SupplyNetwork, load_firms


@pytest.fixture(scope="module")
def network() -> SupplyNetwork:
    return load_firms()


def test_default_network_has_two_firms_per_stage(network: SupplyNetwork) -> None:
    assert sum(len(network.firms_in(stage)) for stage in STAGES) == 8
    assert all(len(network.firms_in(stage)) == 2 for stage in STAGES)


def test_supplier_topology_resolves_to_firms(network: SupplyNetwork) -> None:
    assert all(not firm.suppliers for firm in network.firms_in("factory"))

    for retailer in network.firms_in("retailer"):
        suppliers = network.suppliers_of(retailer.id)
        assert all(isinstance(supplier, Firm) for supplier in suppliers)
        assert all(supplier.stage == "wholesaler" for supplier in suppliers)

    for stage in STAGES[:-1]:
        expected_stage = network.upstream_stage(stage)
        for firm in network.firms_in(stage):
            assert all(
                supplier.stage == expected_stage
                for supplier in network.suppliers_of(firm.id)
            )


def test_archetypes_are_loaded(network: SupplyNetwork) -> None:
    assert network.firm("retailer_a").archetype == "standard"
    assert network.firm("retailer_b").archetype == "low_cost"
    assert network.firm("factory_a").archetype == "premium"


def test_wrong_stage_supplier_raises_value_error() -> None:
    network = load_firms()
    retailer = network.firm("retailer_a").model_copy(
        update={"suppliers": ["factory_a"]}
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
