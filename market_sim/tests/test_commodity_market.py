"""Phase 38 commodity-market price behavior."""

from math import exp

import pytest

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def _env(config=None, days: int = 70) -> MarketEnvironment:
    env = MarketEnvironment(
        load_firms(), config=config, horizon=days, enforce_capacity=True, enable_workforce=True, seed=3,
    )
    env.reset()
    return env


def _orders(env: MarketEnvironment, quantity: int = 30) -> dict[str, int]:
    return {f.id: quantity for s in env.network.stages for f in s.firms}


def test_market_prices_stay_in_band_and_are_seeded() -> None:
    config = load_market_config()
    config = config.model_copy(update={"commodities": config.commodities.model_copy(update={
        "market_enabled": True,
        "market_annual_volatility": 0.5,
    })})
    days = config.simulation.days_per_year
    first = _env(config, days=days * 8)
    second = _env(config, days=days * 8)

    for _ in range(days * 8):
        first.step(0, _orders(first, 30))
        second.step(0, _orders(second, 30))

    # The final boundary update runs at the start of the next step.
    first.step(0, _orders(first, 30))
    second.step(0, _orders(second, 30))

    cfg = first.config.commodities
    assert len(first.commodity_history) == 8 + 1
    assert len(second.commodity_history) == 8 + 1
    for row in first.commodity_history:
        assert all(cfg.market_band_min <= price <= cfg.market_band_max
                   for price in row["prices"].values())
    assert [row["prices"] for row in first.commodity_history] == [
        row["prices"] for row in second.commodity_history
    ]


def test_demand_effect_is_light() -> None:
    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"days_per_year": 20}),
        "commodities": config.commodities.model_copy(update={
            "market_enabled": True,
            "market_annual_volatility": 0.0,
            "market_demand_strength": 0.04,
        }),
        "categories": config.categories.model_copy(update={"enabled": False}),
    })
    days = config.simulation.days_per_year
    env_a = _env(config, days=days * 4 + 1)
    env_b = _env(config, days=days * 4 + 1)

    for env in (env_a, env_b):
        for _ in range(days * 3):
            env.step(0, _orders(env, 30))

    previous_a = dict(env_a.commodity_price)
    previous_b = dict(env_b.commodity_price)

    for _ in range(days):
        env_a.step(0, _orders(env_a, 30))
        env_b.step(0, _orders(env_b, 0))

    # Add extra buying during year four so the demand signal remains clear
    # even when production capacity limits the daily orders.
    # Each raw material is bought explicitly, since every category buys only its own.
    for name in env_a.commodity_price:
        env_a.record_commodity_purchase("x", 1_000_000, name)
    env_a.step(0, _orders(env_a, 30))
    env_b.step(0, _orders(env_b, 0))

    for name, price in env_a.commodity_price.items():
        assert price > 1.0
        assert price <= previous_a[name] * exp(0.04) * 1.0001

    for name, price in env_b.commodity_price.items():
        assert price < previous_b[name]
        assert price >= previous_b[name] * exp(-0.04) * 0.9999
        assert price >= 0.7


def test_market_disabled_keeps_old_behaviour() -> None:
    config = load_market_config()
    config = config.model_copy(update={"commodities": config.commodities.model_copy(update={
        "market_enabled": False,
        "index_volatility": 0.0,
    })})
    days = config.simulation.days_per_year
    env = _env(config, days=days * 2)

    for _ in range(days * 2):
        env.step(0, _orders(env, 30))

    assert len(env.commodity_history) == 1
    assert env.material_cost_per_unit() == pytest.approx(
        config.commodities.category_unit_cost("beer")
    )


def test_firms_pay_market_price() -> None:
    config = load_market_config()
    config = config.model_copy(update={"commodities": config.commodities.model_copy(update={
        "market_enabled": True,
        "market_annual_volatility": 0.0,
    })})
    env = _env(config)
    env.commodity_price["malt"] = 1.4

    expected = sum(
        config.commodities.components[name] * amount * env.commodity_price[name]
        for name, amount in config.commodities.amounts("beer").items()
    )
    assert env.material_cost_per_unit() == pytest.approx(expected)
