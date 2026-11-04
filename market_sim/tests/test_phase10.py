"""Phase 10: marketing, restaurants, minority stakes and new laws."""

import pytest

from market_sim.laws import assess_laws
from market_sim.run import build_runner, run_simulation


def _runner(years=1, days=20):
    runner, _ = build_runner(years, 0, days_per_year=days)
    state = runner.start()
    runner.continue_run(state, years)
    return runner, state


def test_marketing_spending_raises_awareness_and_costs_money():
    runner, state = _runner()
    book, mk = runner.env.brand_book, runner.marketing
    before = book.awareness.get("alpen_gold", runner.config.marketing.start_awareness)
    mk.spent = {"factory_01": 5e8}
    mk.year_end(runner, state)
    assert book.awareness["alpen_gold"] > before * (1 - runner.config.marketing.decay_per_year)
    mk.daily_budget = {"retailer_01": 1000.0}
    cost = runner.env.runtimes["retailer_01"].fixed_cost
    mk.daily(runner.env)
    assert runner.env.runtimes["retailer_01"].fixed_cost == pytest.approx(cost + 1000.0)


def test_advertising_ban_stops_awareness_growth_for_the_category():
    runner, state = _runner()
    book, mk = runner.env.brand_book, runner.marketing
    mk.banned_categories.add("spirits")
    start = book.awareness.get("alpen_kraeuter", runner.config.marketing.start_awareness)
    mk.spent = {"distillery_01": 1e9}
    mk.year_end(runner, state)
    assert book.awareness["alpen_kraeuter"] == pytest.approx(start * (1 - runner.config.marketing.decay_per_year))


def test_restaurants_charge_a_markup_and_serve_part_of_the_demand():
    result = run_simulation(years=2, seed=0, days_per_year=40)
    last = result.system_kpis[-1]
    assert 0.05 < last.restaurant_unit_share < 0.4
    assert last.restaurant_revenue_share > last.restaurant_unit_share  # restaurants sell dearer
    runner, _ = _runner()
    book = runner.env.brand_book
    restaurant, store = runner.network.firm("restaurant_01"), runner.network.firm("retailer_01")
    brand = book.brands["alpen_lager"]
    assert book.retail_price(5.0, brand, restaurant) == pytest.approx(book.retail_price(5.0, brand, store) * 3.0)


def test_young_classes_drink_more_out_of_home():
    runner, _ = _runner()
    book = runner.env.brand_book
    assert book.out_of_home_share(book.classes["income_3_18-34_regular"]) > book.out_of_home_share(book.classes["income_3_65+_regular"])


def test_stakes_pay_dividends_and_count_for_antitrust():
    runner, state = _runner(years=2)
    h = runner.holdings
    owner, target = "wholesaler_01", "wholesaler_02"
    h.stakes = {(owner, target): 0.3}
    assert target in h.antitrust_partners(owner)
    cash = runner.env.runtimes[owner].cash
    state.summaries[-1][target] = state.summaries[-1][target].__class__(
        **{**state.summaries[-1][target].__dict__, "profit": 1e8})
    h.cfg.buy_probability = 0.0
    h.year_end(runner, state)
    assert runner.env.runtimes[owner].cash == pytest.approx(cash + 0.3 * 1e8 * h.cfg.payout_ratio)


def test_law_effects_are_only_reported_when_clear():
    runner, _ = _runner()
    cfg = runner.config.laws
    flat = [{"year": y, "offences": 10.0 + (y % 2) * 0.1} for y in range(1, 13)]
    law = {"name": "kontrollen", "title_de": "Strengere Kontrollen", "year": 6, "watch": ["offences"]}
    early = assess_laws([law], [r for r in flat if r["year"] <= 7], cfg)[0]
    assert early["verdict"] == "Folgen noch unklar"
    assert assess_laws([law], flat, cfg)[0]["verdict"] == "keine klare Folge erkennbar"
    jump = [{**r, "offences": r["offences"] + (5 if r["year"] > 6 else 0)} for r in flat]
    clear = assess_laws([law], jump, cfg)[0]
    assert clear["verdict"] == "Folge erkennbar" and clear["findings"][0]["change"] > 4


def test_minimum_wage_lifts_low_wages():
    runner, state = _runner()
    law = next(l for l in runner.config.laws.laws if l.kind == "minimum_wage")
    runner.laws._enact(runner, law)
    runner.laws.apply_yearly(runner)
    floor = runner.laws.minimum_wage * runner.long_run.price_index
    assert all(f.wage_level >= floor - 1e-9 for f in runner._firms() if runner.env.runtimes[f.id].active)
