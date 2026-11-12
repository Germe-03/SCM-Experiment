"""Feedback 1: Flaschen statt Simulationseinheiten, Kosten- und Engpassansicht, deutsche Kategorien."""

import json

import pytest

from market_sim.game.controller import GameController


@pytest.fixture()
def game(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    controller.end_round({})
    controller.end_round({})  # Jahr 2: erster Jahresabschluss liegt vor
    return controller


def test_unit_size_in_state(game):
    state = game.state()
    assert state["unit_size"] > 1
    kpis = state["kpis"]
    assert "profit_year" in kpis
    assert "capacity_per_day" in kpis and kpis["capacity_per_day"] > 0
    history = state["history"]
    assert all(key in history[-1] for key in ["sales", "demand", "inventory", "backlog"])


def test_revenue_year_matches_runtime(game):
    state = game.state()
    firm_id = game.snapshot.firm_id
    runtime = game.session.runner.env.runtimes[firm_id]
    base = game.session.runner._game_year_marks[firm_id]["values"]["revenue"]
    revenue_year = state["kpis"]["revenue_year"]
    assert abs(revenue_year - (runtime.revenue - base)) < 1.0
    assert revenue_year >= 0


def test_costs_view(game):
    data = game.view("costs")
    assert "error" not in data
    json.dumps(data)
    assert data["items"]
    for item in data["items"]:
        assert all(key in item for key in ["key", "label", "chf_year", "share"])
    assert data["items"] == sorted(data["items"], key=lambda item: item["chf_year"], reverse=True)
    assert data["unit_size"] == game.state()["unit_size"]
    assert all(key in data for key in ["year", "revenue_year", "profit_year"])


def test_bottleneck_view(game):
    data = game.view("bottleneck")
    assert "error" not in data
    json.dumps(data)
    assert data["kind"] in {"personal", "lager", "transport", "nachfrage"}
    assert isinstance(data["text"], str) and data["text"] and "ß" not in data["text"]
    assert all(key in data for key in [
        "capacity_per_day", "demand_per_day", "sales_per_day",
        "transport_per_day", "days_of_stock",
    ])


def test_market_categories_german(game):
    data = game.view("market")
    names = [category["name"] for category in data["categories"]]
    assert "beer" not in names
    if names:
        assert "Bier" in names
