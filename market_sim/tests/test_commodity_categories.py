"""Raw materials per product category and the separate electricity price."""

import pytest

from market_sim.config import load_market_config
from market_sim.environment import MarketEnvironment
from market_sim.models import load_firms


def _env(config=None, days: int = 800) -> MarketEnvironment:
    env = MarketEnvironment(load_firms(), config=config, horizon=days, enforce_capacity=True,
                            enable_workforce=True, seed=3)
    env.reset()
    return env


def test_category_cost_level_matches_old_calibration() -> None:
    cfg = load_market_config().commodities
    for category in ("beer", "wine", "spirits"):
        assert cfg.category_unit_cost(category) == pytest.approx(14000.0)
    assert set(cfg.amounts("wine")) == {"grapes", "packaging", "cork"}
    assert "energy" not in cfg.all_names()


def test_unknown_category_falls_back_and_empty_config_is_old_behaviour() -> None:
    cfg = load_market_config().commodities
    assert cfg.amounts("unbekannt") == cfg.amounts("beer")
    old = cfg.model_copy(update={"components_by_category": {}})
    assert old.amounts("wine") == {name: 1.0 for name in old.components}


def test_purchases_only_of_own_category() -> None:
    env = _env()
    env.record_commodity_purchase("factory_01", 10)
    firm = env.network.firm("factory_01")
    bought = {n for n, v in env.commodity_bought.items() if v > 0}
    assert bought == set(env.config.commodities.amounts(firm.category))


def test_electricity_index_is_seeded_and_in_band() -> None:
    config = load_market_config()
    first, second = _env(config), _env(config)
    for env in (first, second):
        for _ in range(400):
            env.step(0, {f.id: 0 for s in env.network.stages for f in s.firms})
    cfg = config.electricity
    assert first.electricity_log_index == second.electricity_log_index
    assert cfg.band_min <= first.electricity_level() <= cfg.band_max
    assert first.electricity_level() != 1.0


def test_electricity_adds_to_production_cost_and_can_be_off() -> None:
    config = load_market_config()
    env = _env(config)
    firm = env.network.firm("factory_01")
    with_power = env.unit_production_cost(firm)
    env.electricity_log_index = 0.5
    assert env.unit_production_cost(firm) > with_power
    off = config.model_copy(update={"electricity": config.electricity.model_copy(update={"enabled": False})})
    env_off = _env(off)
    assert env_off.unit_production_cost(firm) == pytest.approx(with_power - config.electricity.cost_per_unit)
