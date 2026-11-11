"""Tests for softdrinks and water in the market simulation."""

import pytest

from market_sim.run import build_runner


def _runner(days=10):
    runner, _ = build_runner(1, 0, days_per_year=days)
    state = runner.start()
    return runner, state


def test_categories_loaded():
    runner, _ = _runner()
    book = runner.env.brand_book

    assert set(book.base_share) == {"beer", "wine", "spirits", "softdrinks", "water"}
    assert book.is_alcoholic("softdrinks") is False
    assert book.is_alcoholic("water") is False
    assert book.is_alcoholic("beer") is True
    assert sum(book.base_share.values()) == pytest.approx(1.0)


def test_start_firms_exist():
    runner, _ = _runner()
    book = runner.env.brand_book

    for firm_id in ("softdrink_01", "softdrink_02", "softdrink_03"):
        assert runner.network.firm(firm_id).category == "softdrinks"
    for firm_id in ("spring_01", "spring_02"):
        assert runner.network.firm(firm_id).category == "water"

    softdrink_firms = [
        firm for firm in runner.network.firms_in("factory")
        if firm.category == "softdrinks"
    ]
    water_firms = [
        firm for firm in runner.network.firms_in("factory")
        if firm.category == "water"
    ]
    assert len(softdrink_firms) >= 3
    assert len(water_firms) == 2

    for firm in softdrink_firms:
        brands = book.brands_of(firm.id)
        assert brands
        assert all(book.brands[brand_id].category == "softdrinks" for brand_id in brands)

    for firm in water_firms:
        brands = book.brands_of(firm.id)
        assert brands
        assert all(book.brands[brand_id].category == "water" for brand_id in brands)

    assert runner.network.firm("spring_01").region == "zentralschweiz"


def test_season_summer_above_winter():
    runner, _ = _runner(days=365)
    book = runner.env.brand_book
    summer = 181
    winter = 364

    soft_summer = book.season_factor("softdrinks", summer)
    soft_winter = book.season_factor("softdrinks", winter)
    water_summer = book.season_factor("water", summer)
    water_winter = book.season_factor("water", winter)

    assert soft_summer > soft_winter
    assert water_summer > water_winter
    assert soft_summer - soft_winter > water_summer - water_winter
    assert soft_summer >= 1.05
    assert book.season_factor("beer", summer) == 1.0
    assert book.season_factor("softdrinks", summer, heat=True) > book.season_factor(
        "softdrinks", summer, heat=False
    )


def test_category_shares_age_and_total():
    runner, _ = _runner()
    book = runner.env.brand_book

    young = book.class_shares(book.classes["income_3_18-34_regular"], {})
    older = book.class_shares(book.classes["income_3_65+_regular"], {})

    assert sum(young.values()) == pytest.approx(1.0)
    assert young["softdrinks"] > older["softdrinks"]


def test_sugar_tax_raises_softdrink_cost_not_water():
    runner, _ = _runner()
    env = runner.env
    soft = runner.network.firm("softdrink_01")
    water = runner.network.firm("spring_01")
    cost_soft = env.unit_production_cost(soft)
    cost_water = env.unit_production_cost(water)
    law = next(law for law in runner.config.laws.laws if law.kind == "sugar_tax")

    runner.laws._enact(runner, law)

    assert env.unit_production_cost(soft) == pytest.approx(cost_soft * (1 + law.strength))
    assert env.unit_production_cost(water) == pytest.approx(cost_water)
    assert env.brand_book.law_shift["softdrinks"] < 1
    assert env.brand_book.law_shift["water"] > 1


def test_deposit_raises_both_costs():
    runner, _ = _runner()
    env = runner.env
    soft = runner.network.firm("softdrink_01")
    water = runner.network.firm("spring_01")
    beer = runner.network.firm("factory_01")
    cost_soft = env.unit_production_cost(soft)
    cost_water = env.unit_production_cost(water)
    cost_beer = env.unit_production_cost(beer)
    price_index = env.price_index
    law = next(law for law in runner.config.laws.laws if law.kind == "deposit")

    runner.laws._enact(runner, law)

    expected_increase = law.strength * price_index
    assert env.unit_production_cost(soft) == pytest.approx(cost_soft + expected_increase)
    assert env.unit_production_cost(water) == pytest.approx(cost_water + expected_increase)
    assert env.unit_production_cost(beer) == pytest.approx(cost_beer)
    assert "softdrinks" in env.deposit
    assert "water" in env.deposit


def test_commodities_and_cost_levels():
    runner, _ = _runner()
    cfg = runner.config.commodities

    assert {"sugar", "co2", "pet"} <= set(cfg.all_names())
    assert cfg.category_unit_cost("water") < cfg.category_unit_cost("softdrinks")
    assert cfg.category_unit_cost("softdrinks") < cfg.category_unit_cost("beer")
    assert "pet" in cfg.amounts("water")
    assert "malt" not in cfg.amounts("water")


def test_research_stages_exist():
    runner, _ = _runner()
    trees = runner.config.research.trees["factory"]
    by_name = {stage.name: stage for stage in trees}

    assert "softdrinks_sortiment" not in by_name
    assert by_name["energydrink"].patentable is True
    assert "zuckerreduziert" in by_name
    assert "light_getraenke" in by_name
    assert "natuerliche_suessstoffe" in by_name
    assert by_name["natuerliche_suessstoffe"].requires == ["light_getraenke"]
    assert "quellenausbau" in by_name
    assert "aromawasser" in by_name
    assert "leichtere_pet" in by_name
    assert "abfuellanlage_getraenke" in by_name


def test_short_run_sells_softdrinks_and_water():
    runner, years = build_runner(2, 0, days_per_year=60)
    result = runner.continue_run(runner.start(), years)

    assert sum(
        report["units_sold"]
        for report in result.brand_reports
        if report["category"] == "softdrinks"
    ) > 0
    assert sum(
        report["units_sold"]
        for report in result.brand_reports
        if report["category"] == "water"
    ) > 0
    assert sum(
        report["units_sold"]
        for report in result.brand_reports
        if report["category"] == "beer"
    ) > 0
