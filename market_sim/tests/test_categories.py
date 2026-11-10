"""Phase 4: beer, wine and spirits, wine harvest and maturation, imports and exports."""

import pytest

from market_sim.run import build_runner


def _runner(days=10):
    runner, _ = build_runner(1, 0, days_per_year=days)
    state = runner.start()
    return runner, state


def test_three_categories_and_new_producers_exist():
    runner, _ = _runner()
    book = runner.env.brand_book
    assert set(book.base_share) == {"beer", "wine", "spirits", "softdrinks", "water"}
    categories = {f.id: (f.category, f.importer) for f in runner.network.firms_in("factory")}
    assert categories["winery_01"] == ("wine", False)
    assert categories["importer_02"] == ("wine", True)


def test_richer_classes_drink_more_wine():
    runner, _ = _runner()
    book = runner.env.brand_book
    poor = book.class_shares(book.classes["income_1_35-64_regular"], {})
    rich = book.class_shares(book.classes["income_5_35-64_regular"], {})
    assert rich["wine"] > poor["wine"]
    assert sum(rich.values()) == pytest.approx(1.0)


def test_wine_costs_more_per_unit_than_beer():
    runner, _ = _runner()
    book = runner.env.brand_book
    beer, wine = book.brands["alpen_lager"], book.brands["wallis_rot"]
    assert book.retail_price(5.0, wine) == pytest.approx(book.retail_price(5.0, beer) * 1.6)
    assert book.parcel_value({"alpen_lager": 2, "wallis_rot": 1}, 1.0) == pytest.approx(2 + 1.6)


def test_premium_store_receives_more_wine_than_discounter():
    runner, _ = _runner()
    book = runner.env.brand_book
    stock = {"alpen_lager": 500, "wallis_rot": 500}
    premium = runner.network.firm("retailer_03")
    discount = runner.network.firm("retailer_02")
    to_premium = book.take_for(premium, dict(stock), 100)
    to_discount = book.take_for(discount, dict(stock), 100)
    assert to_premium.get("wallis_rot", 0) > to_discount.get("wallis_rot", 0)
    assert sum(to_premium.values()) == 100


def test_imports_pay_exchange_rate_and_tariff():
    runner, _ = _runner()
    env = runner.env
    importer = runner.network.firm("importer_01")
    cheap = env.unit_production_cost(importer)
    env.fx_rate *= 1.2
    assert env.unit_production_cost(importer) == pytest.approx(cheap * 1.2)


def test_wine_is_pressed_at_harvest_and_released_after_maturing():
    runner, _ = _runner(days=365)
    env = runner.env
    winery = runner.network.firm("winery_02")
    runtime = env.runtimes[winery.id]
    runtime.shipment_history = [10] * 365
    env.period = 100
    assert env._harvest_producer(winery) is True
    queued = len(runtime.maturing)
    env.period = runner.config.categories.harvest_day
    env._harvest_producer(winery)
    assert len(runtime.maturing) > queued
    release, brand_id, units, _ = runtime.maturing[-1]
    assert release == env.period + env.brand_book.brands[brand_id].maturation_days
    before = runtime.inventory
    env.period = release
    env._release_matured()
    # Seeded older vintages may be released on the same day.
    assert runtime.inventory >= before + units


def test_weak_franc_raises_exports():
    def exported(fx):
        runner, _ = _runner()
        env = runner.env
        env.fx_rate = fx
        for firm in runner.network.firms_in("factory"):
            env.runtimes[firm.id].quality_level = 0.9
        env._export()
        return env.brand_book.export_units

    assert exported(1.3) > exported(0.8)
