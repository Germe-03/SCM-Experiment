"""Runtime supplier discovery across active upstream firms."""

from market_sim.environment import MarketEnvironment
from market_sim.models import STAGES, Stage, SupplyNetwork, load_firms


def _replace_firm(network, replacement):
    return SupplyNetwork(stages=[
        Stage(
            name=stage,
            firms=[replacement if firm.id == replacement.id else firm
                   for firm in network.firms_in(stage)],
        )
        for stage in STAGES
    ])


def test_empty_supplier_list_discovers_all_upstream_firms() -> None:
    network = load_firms()
    retailer = network.firm("retailer_01").model_copy(update={"suppliers": []})
    network = _replace_firm(network, retailer)

    assert [firm.id for firm in network.suppliers_of(retailer.id)] == [
        firm.id for firm in network.firms_in("wholesaler")
    ]


def test_non_empty_supplier_list_restricts_runtime_candidates() -> None:
    network = load_firms()
    retailer = network.firm("retailer_01").model_copy(
        update={"suppliers": ["wholesaler_01", "wholesaler_02"]}
    )
    network = _replace_firm(network, retailer)
    env = MarketEnvironment(network)
    env.reset()
    env.runtimes["wholesaler_01"].active = False
    env.close_firm("wholesaler_01")

    assert [firm.id for firm in env.supplier_candidates(retailer.id)] == [
        "wholesaler_02"
    ]

