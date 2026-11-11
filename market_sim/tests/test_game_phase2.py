import importlib
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def controller(tmp_path):
    from market_sim.game.controller import GameController

    return GameController(tmp_path, seed=0, years=1, days_per_year=60)


@pytest.fixture
def http_server(controller):
    try:
        server_module = importlib.import_module("market_sim.game.server")
        make_server = getattr(server_module, "make_server")
    except (ImportError, AttributeError):
        pytest.skip("Der Spielserver ist nicht verfuegbar")

    server = make_server(controller, 0)
    assert isinstance(server, ThreadingHTTPServer)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_messages_for_known_unknown_and_private_events():
    from market_sim.game.messages import message_for, messages_for

    names = {"player": "Testbräu", "other": "Fremdbräu"}

    def event(firm, event_type, details="Ereignisdetails"):
        return {
            "year": 1,
            "day": 3,
            "firm": firm,
            "event": event_type,
            "details": details,
        }

    own_message = message_for(event("player", "price_increase"), "player", names)
    assert own_message["kind"] == "eigen"
    assert own_message["important"] is True

    assert message_for(event("other", "rnd_started"), "player", names) is None
    assert messages_for(
        [event("other", "rnd_started")], "player", names
    ) == []

    market_message = message_for(event("other", "law_enacted"), "player", names)
    assert market_message["kind"] == "markt"
    assert market_message["important"] is True

    unknown_message = message_for(
        event("other", "xyz_unknown", "Unbekannte Details"),
        "player",
        names,
    )
    assert "Unbekannte Details" in unknown_message["text"]

    known_types = [
        "market_entry",
        "bankruptcy",
        "takeover",
        "takeover_blocked",
        "merger_formed",
        "merger_blocked",
        "law_enacted",
        "recession",
        "inflation",
        "policy_rate_emergency",
        "price_increase",
        "poisoning",
        "offence_detected",
        "listed",
        "delisted",
        "exchange_opened",
        "patent_granted",
        "patent_expired",
        "rnd_success",
        "rnd_implemented",
        "loan_granted",
        "credit_rejected",
        "capacity_limit",
        "supplier_switch",
        "transport_switch",
        "trend_change",
        "holding_takeover",
        "holding_sold",
        "stake_bought",
        "stake_sold",
        "player_sale",
        "strategy_change",
    ]
    events = [
        event(firm, event_type)
        for event_type in known_types
        for firm in ("player", "other")
    ]
    messages = messages_for(events, "player", names)
    assert messages
    assert all("ß" not in message["text"] for message in messages)


def test_controller_new_game_round_and_errors(controller):
    state = controller.new_game("hersteller", "Testbräu")

    assert state["running"] is True
    assert state["game_over"] is False
    assert state["year"] == 1
    assert state["month"] == 1
    assert state["kpis"]["cash"] > 0

    price_band = state["price_band"]
    assert price_band["min"] < price_band["max"]
    price = (price_band["min"] + price_band["max"]) / 2

    next_state = controller.end_round({"base_price": price})
    assert next_state["month"] == 2
    assert next_state["settings"]["base_price"] == pytest.approx(price)

    invalid_settings = controller.end_round({"foo": 1})
    assert "error" in invalid_settings

    invalid_branch = controller.new_game("ungueltige_branche", "Testbräu")
    assert "error" in invalid_branch


def test_save_and_load_restore_game(controller):
    controller.new_game("hersteller", "Testbräu")
    controller.end_round()

    before = controller.state()
    save_result = controller.save("t1")
    assert save_result.get("ok") is True
    assert any(item["name"] == "t1" for item in controller.saves()["saves"])

    loaded = controller.load("t1")
    assert loaded["year"] == before["year"]
    assert loaded["month"] == before["month"]
    assert loaded["kpis"]["cash"] == pytest.approx(before["kpis"]["cash"])
    assert len(loaded["history"]) == len(before["history"])


def test_sell_ends_game_and_prevents_saving(controller):
    controller.new_game("hersteller", "Testbräu")

    state = controller.sell()
    assert state["game_over"] is True
    assert state["reason"] == "verkauft"
    assert state["sale"]["price"] >= 0

    assert "error" in controller.save("x")


def test_game_server_options_and_home_page(http_server):
    base_url = f"http://127.0.0.1:{http_server.server_address[1]}"

    with urllib.request.urlopen(f"{base_url}/api/options") as response:
        options = json.loads(response.read().decode("utf-8"))
    assert len(options["branches"]) == 5

    with urllib.request.urlopen(f"{base_url}/") as response:
        html = response.read().decode("utf-8")
    assert "<html" in html.lower()
