"""Phase 2: consumer classes in consumers.yaml."""

import pytest

from market_sim.config import load_market_config


def test_thirty_classes_match_population_and_annual_demand():
    config = load_market_config()
    classes = config.consumers.classes
    assert len(classes) == 30
    assert sum(c.persons for c in classes) == pytest.approx(7_500_000, rel=1e-4)
    units = sum(c.persons * c.units_per_person_per_year for c in classes) / config.unit_scale.real_units_per_sim_unit
    assert units == pytest.approx(config.demand.annual_demand_units, rel=1e-3)


def test_richer_classes_pay_more_and_care_less_about_price():
    classes = {c.name: c for c in load_market_config().consumers.classes}
    poor, rich = classes["income_1_35-64_regular"], classes["income_5_35-64_regular"]
    assert poor.max_price < rich.max_price
    assert poor.weights.price > rich.weights.price
