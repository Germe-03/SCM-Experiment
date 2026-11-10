"""Unit tests for the reworked Post market."""

from types import SimpleNamespace

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner


def _config(**post):
    config = load_market_config()
    carriers = config.carriers.model_copy(update={
        "enabled": True,
        "post": config.carriers.post.model_copy(update=post),
        "couriers": config.carriers.couriers.model_copy(update={"enabled": False}),
    })
    return config.model_copy(update={"carriers": carriers})


def _market(config=None):
    if config is None:
        config = _config()
    runner, _ = build_runner(1, 0, days_per_year=30, config=config)
    runner.start()
    return runner, runner.env.geography.carriers


def _simulate_year(market, runner, year, volume, load_days=0.0):
    market.post.days = market.days_per_year
    market.post.fuel_km = volume
    market.post.unit_km = volume
    market.post.revenue = market.post.tariff * volume
    market.post.load_days = load_days
    state = SimpleNamespace(year=year, events=[])
    fake_runner = SimpleNamespace(
        long_run=SimpleNamespace(price_index=1.0),
        env=runner.env,
    )
    market.year_end(fake_runner, state)
    return state


def test_start_tariff_covers_costs_at_start_volume():
    # The reserve nudge (Phase 54) is off here: the artificial first year has no network cost yet.
    runner, market = _market(_config(reserve_adjust=0.0))
    volume = 1e7

    _simulate_year(market, runner, 1, volume)

    assert market.network_per_day * market.days_per_year == pytest.approx(
        market.fixed_rate * volume
    )
    assert market.post.tariff == pytest.approx(market.cfg.post.start_rate, rel=0.01)
    assert market.reports[-1]["bundesbeitrag"] == 0


def test_tariff_stays_bounded_when_volume_drops():
    runner, market = _market()
    volume = 1e7
    _simulate_year(market, runner, 1, volume)
    network_after_start = market.network_per_day
    tariffs = [market.post.tariff]

    for year in range(2, 17):
        previous_tariff = market.post.tariff
        _simulate_year(market, runner, year, 2e6)
        tariffs.append(market.post.tariff)
        assert abs(market.post.tariff / previous_tariff - 1) <= 0.05 + 1e-9

    assert market.post.tariff < 2.0
    assert market.network_per_day < 0.4 * network_after_start
    assert all(
        later <= earlier + 1e-6
        for earlier, later in zip(tariffs[-3:], tariffs[-2:])
    )


def test_fixed_costs_shrink_with_delay():
    runner, market = _market()
    _simulate_year(market, runner, 1, 1e7)
    network_after_start = market.network_per_day

    _simulate_year(market, runner, 2, 2e6)

    target = max(
        market.cfg.post.fixed_cost_per_day,
        market.fixed_rate * market.smoothed_fuel_km / market.days_per_year,
    )
    assert target < market.network_per_day < network_after_start


def test_capacity_gets_headroom_from_start_volume():
    config = _config(capacity_per_day=10.0, expand_utilization=100.0)
    runner, market = _market(config)
    load_days = 100 * market.days_per_year

    _simulate_year(market, runner, 1, 1e7, load_days=load_days)

    assert market.post.capacity_per_day >= 150


def test_carrier_config_defaults():
    config = load_market_config()

    assert config.carriers.enabled is True
    assert config.carriers.couriers.enabled is True


def test_post_reserve_pays_losses_before_the_bund():
    runner, market = _market(_config(reserve_adjust=0.0))
    volume = 1e7
    _simulate_year(market, runner, 1, volume)
    assert market.reserve > 0
    reserve = market.reserve

    # A loss smaller than the reserve is paid from it, the Bund pays nothing.
    market.post.days = market.days_per_year
    market.post.fuel_km = market.post.unit_km = volume
    market.post.revenue = market.fixed_cost_year(runner) * 0 + 0.9 * volume + market.fixed_cost_year(
        SimpleNamespace(long_run=SimpleNamespace(price_index=1.0))) - 0.5 * reserve
    state = SimpleNamespace(year=2, events=[])
    market.year_end(SimpleNamespace(long_run=SimpleNamespace(price_index=1.0), env=runner.env), state)
    row = market.reports[-1]
    assert row["bundesbeitrag"] == 0
    assert row["reserve"] == pytest.approx(0.5 * reserve, rel=0.01)

    # A loss larger than the reserve is covered by the Bund for the rest only.
    market.post.days = market.days_per_year
    market.post.fuel_km = market.post.unit_km = volume
    market.post.revenue = 0.0
    market.year_end(SimpleNamespace(long_run=SimpleNamespace(price_index=1.0), env=runner.env),
                    SimpleNamespace(year=3, events=[]))
    row = market.reports[-1]
    assert row["reserve"] == 0
    assert row["bundesbeitrag"] == pytest.approx(-row["profit"] - 0.5 * reserve, rel=0.01)
