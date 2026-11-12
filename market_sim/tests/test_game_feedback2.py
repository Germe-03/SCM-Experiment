"""Feedback 2: Jahres-KPIs, Optionen, Ansichten, Prüfungen und Meldungen."""

import http.client
import json
import threading

import pytest

from market_sim.game.controller import GameController


@pytest.fixture()
def game(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    controller.end_round({})
    controller.end_round({})
    return controller


def test_state_contains_yearly_kpis_and_game_metadata(game):
    state = game.state()

    assert isinstance(state["kpis"]["revenue_last_year"], (int, float))
    assert isinstance(state["kpis"]["profit_last_year"], (int, float))
    assert isinstance(state["month_name"], str)
    assert state["years_total"] == 2
    assert isinstance(state["years_left"], int)
    assert state["years_left"] in {1, 2}
    assert state["end_reason_text"] is None

    sell_price = state.get("sell_price")
    if sell_price is not None:
        assert sell_price == round(sell_price, 2)


def test_options_include_year_choices_and_regions(game):
    options = game.options()

    assert options["years_choices"] == [5, 10, 20, 30, 40, 50]
    assert isinstance(options["region_labels"], dict)


def test_new_game_year_validation(tmp_path):
    controller = GameController(tmp_path, seed=0, days_per_year=60)
    result = controller.new_game("hersteller", "X", category="beer", years=7)

    assert "error" in result

    controller = GameController(tmp_path, seed=0, days_per_year=60)
    result = controller.new_game("hersteller", "X", category="beer", years=5)

    assert "error" not in result
    assert controller.state()["years_total"] == 5


def test_order_quantity_uses_bottles_and_empty_clears_setting(game):
    unit = game.state()["unit_size"]

    game.end_round({"order_qty": unit * 3 + 1})
    assert game.state()["settings"]["order_qty"] == 4 * unit

    game.end_round({"order_qty": ""})
    assert game.state()["settings"]["order_qty"] is None


def test_views_return_dicts_and_expected_data(game):
    views = {
        name: game.view(name)
        for name in (
            "calculation",
            "pricing",
            "financials",
            "reports",
            "assortment",
            "takeover_offers",
        )
    }
    assert all(isinstance(data, dict) for data in views.values())

    assortment = views["assortment"]
    assert isinstance(assortment["categories"], list)
    assert len(assortment["categories"]) == 5
    assert all(
        {"key", "name", "share_market", "share_mine", "stock_bottles"} <= category.keys()
        for category in assortment["categories"]
    )

    takeover_offers = views["takeover_offers"]
    assert "offers" in takeover_offers
    assert isinstance(takeover_offers["offers"], list)

    financials = views["financials"]
    if "error" not in financials:
        assert {
            "income_current",
            "income_last",
            "balance",
            "cash_flow",
            "ratios",
        } <= financials.keys()


def test_check_reports_warnings_and_requires_game(game, tmp_path):
    result = game.check({"order_qty": 10**9}, {}, {})

    assert "warnings" in result
    assert isinstance(result["warnings"], list)
    assert any(
        warning.get("level") in {"gelb", "rot"} and isinstance(warning.get("text"), str)
        for warning in result["warnings"]
    )

    controller = GameController(tmp_path, seed=0, days_per_year=60)
    assert "error" in controller.check()


def test_server_static_cache_header_and_check_api(game):
    from market_sim.game.server import make_server

    server = make_server(game, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        connection = http.client.HTTPConnection(host, port, timeout=5)

        connection.request("GET", "/cockpit.html")
        response = connection.getresponse()
        response.read()
        assert response.getheader("Cache-Control") == "no-store"

        body = json.dumps({"settings": {"order_qty": 1_000_000_000}})
        connection.request(
            "POST",
            "/api/check",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        result = json.loads(response.read().decode("utf-8"))
        assert "warnings" in result
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture()
def game_with_three_years(tmp_path):
    controller = GameController(tmp_path, seed=0, years=3, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    controller.end_round({})
    controller.end_round({})
    return controller


def test_takeover_offer_message(game_with_three_years):
    runner = game_with_three_years.session.runner
    firm_id = game_with_three_years.snapshot.firm_id
    target_id = next(
        (firm.id for firm in runner._firms() if firm.id != firm_id),
        None,
    )
    if target_id is None:
        pytest.skip("Keine andere aktive Firma für ein Verkaufsangebot vorhanden")

    runner.takeover_offers = [
        {
            "target": target_id,
            "name": "Testfirma",
            "stage": "factory",
            "price": 12345.0,
            "year": 2,
            "reason": "angeschlagen",
        }
    ]

    game_with_three_years.end_round({})
    state = game_with_three_years.state()
    if state["end_reason_text"] is not None:
        pytest.skip("Das Spiel ist nach end_round bereits beendet")

    texts = [
        message if isinstance(message, str) else message.get("text", "")
        for message in state["messages"]
    ]
    assert any("Verkaufsangebot" in text for text in texts)


def test_dividend_message_contains_details():
    from market_sim.game.messages import message_for

    message = message_for(
        {
            "year": 1,
            "day": 3,
            "firm": "p",
            "event": "dividend_received",
            "details": "Dividende 1'000 CHF",
        },
        "p",
        {},
    )

    assert "Dividende" in message["text"]
    assert "1'000" in message["text"]
