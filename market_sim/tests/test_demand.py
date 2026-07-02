"""S5 tests for attractiveness-based consumer demand and lost sales."""

from __future__ import annotations

import pytest

from market_sim.config import AttractivenessWeights, load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def _market(inventories: tuple[int, int] = (100, 100)) -> MarketEnvironment:
    network = load_firms()
    market = MarketEnvironment(
        network, consumer_demand_mode="attractiveness_lost", horizon=1
    )
    market.reset()
    retailers = sorted(network.firms_in("retailer"), key=lambda item: item.id)
    for firm in retailers:
        market.runtimes[firm.id].inventory = 0
        firm.capacity = 1_000
    for firm, inventory in zip(retailers, inventories):
        market.runtimes[firm.id].inventory = inventory
    return market


def test_cheaper_higher_quality_retailer_gets_larger_share() -> None:
    market = _market()
    retailer_a, retailer_b = sorted(
        market.network.firms_in("retailer"), key=lambda firm: firm.id
    )[:2]
    retailer_a.sell_price, retailer_a.quality_level = 2.0, 0.9
    retailer_b.sell_price, retailer_b.quality_level = 8.0, 0.2

    _, info = market.step(101, {})

    assert info["consumer_demand_shares"][retailer_a.id] > info["consumer_demand_shares"][retailer_b.id]


@pytest.mark.parametrize(
    ("demand", "inventories"),
    [(0, (0, 0)), (1, (1, 0)), (17, (3, 20)), (100, (20, 30)), (259, (500, 500))],
)
def test_consumer_demand_is_conserved(demand: int, inventories: tuple[int, int]) -> None:
    market = _market(inventories)
    _, info = market.step(demand, {})
    assert info["consumer_units_sold_total"] + info["lost_sales"] == demand


def test_spillover_uses_other_retailers_remaining_stock() -> None:
    market = _market((0, 100))
    _, info = market.step(80, {})

    retailers = sorted(market.network.firms_in("retailer"), key=lambda firm: firm.id)
    stocked_out, stocked = retailers[:2]
    own_share = info["consumer_demand_shares"][stocked.id]
    assert info["consumer_units_sold"][stocked.id] > own_share
    assert info["lost_sales"] == 0
    assert info["lost_sales"] < info["consumer_demand_shares"][stocked_out.id]


def test_all_retailers_stocked_out_means_all_demand_is_lost() -> None:
    market = _market((0, 0))
    _, info = market.step(73, {})
    assert info["consumer_units_sold_total"] == 0
    assert info["lost_sales"] == 73


def test_scores_are_bounded_and_zero_scores_fall_back_to_equal_split() -> None:
    market = _market((10_000, 10_000))
    retailer_a, retailer_b = sorted(
        market.network.firms_in("retailer"), key=lambda firm: firm.id
    )[:2]
    retailer_a.sell_price = -1_000
    retailer_b.sell_price = 1_000
    assert market._consumer_price_score(retailer_a.sell_price) == 1.0
    assert market._consumer_price_score(retailer_b.sell_price) == 0.0
    assert market._consumer_availability_score(-10, 5) == 0.0
    assert market._consumer_availability_score(10_000, 5) == 1.0
    scores = market._consumer_attractiveness(10)
    assert all(0.0 <= score <= 1.0 for score in scores.values())

    weights = AttractivenessWeights(price=1, quality=0, reputation=0, availability=0)
    market.config = load_market_config().model_copy(
        update={"demand_attractiveness_weights": weights}
    )
    retailers = market.network.firms_in("retailer")
    for retailer in retailers:
        retailer.sell_price = market.config.price.max
    shares, sold, lost = market._fulfill_consumer_demand(5)
    assert set(shares) == {retailer.id for retailer in retailers}
    assert sum(shares.values()) == 5
    assert max(shares.values()) - min(shares.values()) <= 1
    assert sum(sold.values()) + lost == 5


def test_result_exposes_cumulative_sales_and_lost_sales() -> None:
    market = _market((2, 3))
    market.step(10, {})
    result = market.get_result()
    assert result.cumulative_lost_sales == 5
    assert sum(
        result.firm_results[firm.id].cumulative_consumer_units_sold
        for firm in market.network.firms_in("retailer")
    ) == 5
