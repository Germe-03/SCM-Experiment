"""Cockpit 2: Datenansichten, Wirkungsprotokoll, neue Aufträge und Graubereich mit Intensität."""

import json

import pytest

from market_sim.game.choices import PlayerChoices
from market_sim.game.controller import GameController

VIEWS = ["compare", "capacity", "market", "suppliers", "population", "swiss_map", "macro",
         "banks", "stocks", "commodities", "trucks", "research_tree", "autopilot",
         "classification", "glossary"]


@pytest.fixture()
def game(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    controller.end_round({})
    controller.end_round({})  # Jahr 2: erster Jahresabschluss liegt vor
    return controller


def test_all_views_work_and_hide_rival_profits(game):
    player = game.snapshot.firm_id
    for name in VIEWS:
        data = game.view(name)
        assert "error" not in data, (name, data)
        json.dumps(data)
    rows = game.view("compare")["rows"]
    assert any(row["is_player"] for row in rows)
    for row in rows:
        if row["id"] != player:
            assert "profit" not in row and "cash" not in row
    assert game.view("nonsense")["error"]


def test_capacity_and_map_have_ranges(game):
    capacity = game.view("capacity")
    assert capacity["demand"]["min"] <= capacity["demand"]["avg"] <= capacity["demand"]["max"]
    assert capacity["capacity_per_day"] > 0
    swiss = game.view("swiss_map")
    assert len(swiss["outline"]) > 10 and swiss["regions"]


def test_effects_warnings_and_change_log(game):
    price = game.snapshot.settings.base_price
    state = game.end_round({"base_price": round(price * 1.1, 2)})
    assert state["effects"][0]["changes"][0].startswith("Preis")
    assert isinstance(state["warnings"], list)
    assert state["classification"]


def test_loan_order_and_research_choice(game):
    state = game.end_round({}, None, {"loan": {"amount": 1_000_000}})
    assert state["order_results"] and "message" in state["order_results"][0]
    tree = game.view("research_tree")
    available = [s["name"] for s in tree["stages"] if s["status"] == "available"]
    if available:
        state = game.end_round({}, {"research_target": available[0]})
        assert state["choices"]["research_target"] == available[0]


def test_offence_intensity():
    choice = PlayerChoices(offences={"lohndumping": 0.3})
    assert choice.offence_intensity("lohndumping") == pytest.approx(0.3)
    assert choice.offence_intensity("pfusch") == 0.0
    assert PlayerChoices(offences=["pfusch"]).offence_intensity("pfusch") == 1.0


def test_supplier_rule_and_marketing_choices_are_accepted(game):
    state = game.end_round({}, {"supplier_rule": "price", "marketing_focus": 0.7,
                                "marketing_target": "18-34"})
    assert state["choices"]["supplier_rule"] == "price"
    assert state["choices"]["marketing_focus"] == pytest.approx(0.7)
