import json

import pytest

from market_sim.game.controller import GameController


@pytest.fixture()
def game(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    return controller


def test_production_view_fields(game):
    data = game.view("production")
    assert "error" not in data, data
    for key in ("capacity_per_day", "producible_per_day", "materials", "cost_per_bottle", "sell_price",
                "margin_per_bottle", "break_even_price", "orders_per_day", "stock_bottles", "days_of_cover"):
        assert key in data
    for key in ("materials", "energy", "wages", "fixed", "handling", "total"):
        assert key in data["cost_per_bottle"]
    assert data["capacity_per_day"] > 0
    assert data["materials"]
    for row in data["materials"]:
        assert row["price_trend"] in ("günstig", "teuer", "im Schnitt")
    json.dumps(data)


def test_production_follows_capacity(game):
    runner = game.session.runner
    firm_id = game.snapshot.firm_id
    policy = runner.policies[firm_id]
    capacity = runner.env._effective_capacity(firm_id)
    firm = runner.network.firm(firm_id)
    strategy = policy.decide_annual(firm, None, runner.config)
    decision = policy.decide_daily(firm, None, strategy, runner.config)
    assert decision.order_qty == capacity
    before = runner.env.runtimes[firm_id].inventory
    game.end_round({})
    after = game.session.runner.env.runtimes[firm_id].inventory
    assert after != before or game.view("production")["producible_per_day"] == 0


def test_brand_marketing_json(game):
    data = game.view("brand_marketing")
    assert "error" not in data, data
    assert any(row["is_mine"] for row in data["brands"])
    json.dumps(data)


def test_contracts_view_robust(game):
    data = game.view("contracts")
    assert "error" not in data, data
    for key in ("partners", "active", "offers", "proposed"):
        assert key in data
    json.dumps(data)
    game.end_round({}, None, {"contract_accept": 999})  # unbekannter Vertrag darf nichts zerstören
    assert "error" not in game.view("contracts")
