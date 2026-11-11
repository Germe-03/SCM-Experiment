"""Spielmodus Phase 6: Rückblick nach Spielende und Wettbewerbsgrenze bei Käufen."""

from market_sim.game import holding_player
from market_sim.game.controller import GameController


def _play_to_end(controller, first=None):
    state = controller.end_round({"base_price": first} if first else {})
    for _ in range(50):
        if state.get("game_over"):
            return state
        state = controller.end_round({})
    raise AssertionError("Spiel endet nicht")


def test_review_after_normal_end(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    start = controller.new_game("hersteller", "Testbräu", category="beer")
    state = _play_to_end(controller, round(start["settings"]["base_price"] * 1.2, 2))
    review = state["review"]
    assert review is not None and review["years"] == 2
    assert 1 <= review["rank"] <= review["of"]
    assert len(review["curves"]["player_revenue"]) == 2
    assert any("Preis" in d for d in review["decisions"])
    assert "ß" not in review["summary"]


def test_review_after_sale(tmp_path):
    controller = GameController(tmp_path, seed=0, years=1, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    state = controller.sell()
    assert state["review"]["player"]["value"] == state["sale"]["price"]
    assert "verkauft" in state["review"]["summary"]


def test_competition_limit_blocks_big_purchase(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    controller.end_round({})
    controller.end_round({})  # Jahr 2: erster Jahresabschluss liegt vor
    session = controller.session
    runner, state = session.runner, session.state
    runner.config.mergers.max_market_share = 0.0  # jede Übernahme wäre zu gross
    target = holding_player.buy_targets(runner, state, controller.snapshot.firm_id)[0]
    runner.env.runtimes[controller.snapshot.firm_id].adjust_cash(1e12, "test")
    result = holding_player.buy(runner, state, controller.snapshot.firm_id, target["id"], 2, 0)
    assert result["ok"] is False and "Wettbewerbsbehörde" in result["message"]
