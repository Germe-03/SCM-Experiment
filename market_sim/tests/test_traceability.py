"""Phase 9: decision log, exit analysis, regional sales and personas."""

import pytest

from market_sim.config import load_market_config
from market_sim.personas import generate_personas
from market_sim.run import run_simulation


@pytest.fixture(scope="module")
def result():
    return run_simulation(years=3, seed=0, days_per_year=40)


def test_yearly_and_monthly_decisions_are_logged(result):
    kinds = {d["decision"] for d in result.decisions}
    assert {"price_band", "wage_level", "r_and_d_budget", "archetype"} <= kinds
    monthly = [d for d in result.decisions if d["month"] is not None]
    assert monthly and all(1 <= d["month"] <= 12 for d in monthly)
    assert {d["decision"] for d in monthly} == {"average_order_quantity", "average_sell_price"}


def test_offence_decisions_carry_the_firms_own_estimate(result):
    offences = [d for d in result.decisions if d["decision"] == "offence"]
    assert offences
    value = offences[0]["value"]
    assert {"committed", "believed_detection_probability", "believed_fine", "expected_gain"} <= set(value)


def test_every_exit_gets_an_analysis_with_a_german_summary():
    config = load_market_config()
    config.bank.restructuring = False
    run = run_simulation(years=6, seed=1, days_per_year=40, config=config)
    assert set(run.exit_analysis) == set(run.exits)
    for firm_id, analysis in run.exit_analysis.items():
        assert analysis["exit_year"] == run.exits[firm_id]
        assert analysis["summary_de"].startswith(run.network.firm(firm_id).name)
        assert len(analysis["drivers"]) <= 3


def test_regional_revenue_adds_up_to_consumer_revenue(result):
    for year in range(1, result.years + 1):
        regional = sum(r["consumer_revenue"] for r in result.region_reports if r["year"] == year)
        stores = sum(result.annual_reports[year - 1][f.id].revenue for f in result.network.firms_in("retailer"))
        assert regional == pytest.approx(stores, rel=1e-6)


def test_two_personas_per_class_one_woman_one_man_and_deterministic(result):
    config = load_market_config()
    personas = result.personas
    assert len(personas) == 2 * len(config.consumers.classes)
    for cls in config.consumers.classes:
        genders = sorted(p["gender"] for p in personas if p["consumer_class"] == cls.name)
        assert genders == ["man", "woman"]
    again = generate_personas(config, 0, result.class_reports, result.brand_reports)
    assert again == personas
    names = config.personas.first_names
    assert all(p["first_name"] in names[p["gender"]] for p in personas)
