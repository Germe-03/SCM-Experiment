"""Phase 39 factory raw-material stock behavior."""

import pytest

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def _config(
    *,
    stockpile_enabled: bool = True,
    stock_spoilage_per_year: dict[str, float] | None = None,
):
    config = load_market_config()
    commodities = {
        "market_enabled": True,
        "stockpile_enabled": stockpile_enabled,
        "market_annual_volatility": 0.0,
        "market_demand_strength": 0.0,
    }
    if stock_spoilage_per_year is not None:
        commodities["stock_spoilage_per_year"] = stock_spoilage_per_year
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"days_per_year": 20}),
        "commodities": config.commodities.model_copy(update=commodities),
    })
    config.categories.enabled = False
    return config


def _env(config=None, days: int = 70) -> MarketEnvironment:
    env = MarketEnvironment(
        load_firms(), config=config, horizon=days, enforce_capacity=True, enable_workforce=True, seed=3,
    )
    env.reset()
    return env


def _orders(env: MarketEnvironment, quantity: int = 20) -> dict[str, int]:
    return {f.id: quantity for s in env.network.stages for f in s.firms}


def _two_years_of_orders(config) -> MarketEnvironment:
    days = config.simulation.days_per_year
    env = _env(config, days=days * 5)
    for _ in range(days * 2):
        env.step(0, _orders(env, 20))
    return env


def _set_factory_cash(env: MarketEnvironment) -> None:
    for firm_id in ("factory_01", "factory_02"):
        env.runtimes[firm_id].cash = 1e9


def test_buys_ahead_when_price_below_average() -> None:
    config = _config()
    env = _two_years_of_orders(config)
    baseline = _two_years_of_orders(config)
    _set_factory_cash(env)
    _set_factory_cash(baseline)

    env.commodity_price["malt"] = 0.8
    env.commodity_price["hops"] = 0.8
    env.commodity_courage["factory_01"] = 1.0
    baseline.commodity_courage["factory_01"] = 1.0

    for _ in range(3):
        env.step(0, _orders(env, 20))
        baseline.step(0, _orders(baseline, 20))

    stock = env.commodity_stock["factory_01"]
    assert stock.get("malt", 0.0) > 0
    assert stock.get("energy", 0.0) == 0
    assert "energy" not in stock
    assert env.commodity_bought["malt"] > baseline.commodity_bought["malt"]
    assert baseline.commodity_stock.get("factory_01", {}) == {}


def test_no_stockpiling_when_price_above_average() -> None:
    env = _two_years_of_orders(_config())
    _set_factory_cash(env)
    env.commodity_price["malt"] = 1.2
    env.commodity_price["hops"] = 1.2
    env.commodity_courage["factory_01"] = 1.0

    for _ in range(3):
        env.step(0, _orders(env, 20))

    assert not any(env.commodity_stock.get("factory_01", {}).values())


def test_courage_changes_stock() -> None:
    config = _config()
    bold = _two_years_of_orders(config)
    cautious = _two_years_of_orders(config)
    _set_factory_cash(bold)
    _set_factory_cash(cautious)

    for env in (bold, cautious):
        env.commodity_price["malt"] = 0.95
        env.commodity_price["hops"] = 0.95
    bold.commodity_courage["factory_01"] = 1.0
    cautious.commodity_courage["factory_01"] = 0.0

    for _ in range(3):
        bold.step(0, _orders(bold, 20))
        cautious.step(0, _orders(cautious, 20))

    assert bold.commodity_stock["factory_01"].get("malt", 0.0) > 0
    assert not any(cautious.commodity_stock.get("factory_01", {}).values())


def test_stock_is_used_first_and_spoils() -> None:
    config = _config(stock_spoilage_per_year={"malt": 0.05, "hops": 0.25})
    env = _env(config)
    env.commodity_stock["factory_01"] = {"malt": 100.0, "hops": 100.0}
    env.commodity_price["malt"] = 1.0
    env.commodity_price["hops"] = 1.0
    env.commodity_courage["factory_01"] = 0.5

    env.step(0, _orders(env, 20))
    stock = env.commodity_stock["factory_01"]
    assert stock["malt"] < 100.0
    assert stock["hops"] < 100.0

    malt_before_spoilage = stock["malt"]
    hops_before_spoilage = stock["hops"]
    for _ in range(10):
        env.step(0, _orders(env, 0))

    stock = env.commodity_stock["factory_01"]
    assert stock["hops"] / hops_before_spoilage < stock["malt"] / malt_before_spoilage < 1.0
    assert env.runtimes["factory_01"].paid_to["rohstoffe"] > 0


def test_extra_purchases_feed_demand() -> None:
    stock_config = _config(stockpile_enabled=True)
    no_stock_config = _config(stockpile_enabled=False)
    stock_env = _two_years_of_orders(stock_config)
    no_stock_env = _two_years_of_orders(no_stock_config)
    _set_factory_cash(stock_env)
    _set_factory_cash(no_stock_env)

    for env in (stock_env, no_stock_env):
        env.commodity_price["malt"] = 0.8
        env.commodity_price["hops"] = 0.8
    stock_env.commodity_courage["factory_01"] = 1.0

    for _ in range(3):
        stock_env.step(0, _orders(stock_env, 20))
        no_stock_env.step(0, _orders(no_stock_env, 20))

    assert stock_env.commodity_bought["malt"] > no_stock_env.commodity_bought["malt"]


def test_stockpile_off_keeps_phase38() -> None:
    config = _config(stockpile_enabled=False)
    env = _env(config)
    env.step(0, _orders(env, 20))

    assert env.commodity_stock == {}
    assert env.runtimes["factory_01"].purchase_cost == pytest.approx(
        20 * (env.material_cost_per_unit() + env.electricity_cost_per_unit())
    )


def test_commodity_rows_have_firm_snapshot() -> None:
    env = _env(_config())
    env.step(0, _orders(env, 20))

    firm_snapshot = env.commodity_rows()[-1]["firms"]["factory_01"]
    assert {"stock", "avg_price", "units"} <= firm_snapshot.keys()
