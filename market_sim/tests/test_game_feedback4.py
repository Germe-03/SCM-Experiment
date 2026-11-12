import json
from dataclasses import fields

import pytest

from market_sim.game.controller import GameController


@pytest.mark.parametrize(
    ("branch", "kind"),
    [("detailhaendler", "haendler"), ("hersteller", "hersteller")],
)
def test_views_json_and_fields(tmp_path, branch, kind):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game(branch, "Testfirma")

    for round_number in range(3):
        inventory = game.view("inventory")
        brand_sources = game.view("brand_sources")

        assert isinstance(inventory, dict)
        assert "error" not in inventory
        json.dumps(inventory)
        assert inventory["kind"] == kind
        assert {
            "bottles",
            "value_chf",
            "capacity",
            "used",
            "days_of_cover",
            "in_transit",
        } <= inventory["summary"].keys()
        assert {
            "summary",
            "brands",
            "components",
            "history",
            "warnings",
        } <= inventory.keys()
        assert isinstance(inventory["components"], list)
        if kind == "haendler":
            assert inventory["components"] == []

        assert isinstance(brand_sources, dict)
        assert "error" not in brand_sources
        json.dumps(brand_sources)
        assert isinstance(brand_sources["brands"], dict)
        assert isinstance(brand_sources["by_supplier"], list)

        if round_number < 2:
            game.end_round({})

    assert inventory["history"]
    assert all("label" in row for row in inventory["history"])


def test_brand_suppliers_become_supplier_shares(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testfirma")

    supplier_ids = [c["id"] for c in game.view("suppliers")["candidates"]]
    brand_ids = [brand["id"] for brand in game.view("purchasing")["brands"]]
    if len(supplier_ids) < 2 or len(brand_ids) < 2:
        pytest.skip("Mindestens zwei Lieferanten und Marken erforderlich")

    s1, s2 = supplier_ids[:2]
    b1, b2 = brand_ids[:2]
    game.end_round(
        {},
        {
            "brand_plan": {b1: 100, b2: 300},
            "brand_suppliers": {b1: s1, b2: s2},
        },
    )

    choices = game.state()["choices"]
    assert choices["supplier_shares"] == {s1: 100.0, s2: 300.0}
    assert choices["brand_suppliers"] == {b1: s1, b2: s2}


def test_supplier_shares_remain_none_without_brand_suppliers(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testfirma")
    game.end_round({})

    assert game.state()["choices"]["supplier_shares"] is None


def test_player_choices_brand_suppliers_defaults_to_none(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testfirma")

    choices = game.session.runner.player_choices[game.snapshot.firm_id]
    brand_suppliers = next(
        field for field in fields(type(choices)) if field.name == "brand_suppliers"
    )
    assert brand_suppliers.default is None
