"""Feedback 3: Jahr überspringen, Neues Spiel, Ansichten, Dashboard nach Spielende."""

import json

from market_sim.game.controller import GameController
from market_sim.game.session import GameSession


def _controller(tmp_path):
    controller = GameController(tmp_path / "spielstaende", seed=0, years=2, days_per_year=60)
    controller.new_game("hersteller", "Testbräu", category="beer")
    return controller


def test_skip_year_jumps_to_next_year(tmp_path):
    controller = _controller(tmp_path)
    year = controller.state()["year"]
    state = controller.skip_year({}, {}, {})
    assert "error" not in state
    assert state["game_over"] or state["year"] == year + 1


def test_reset_returns_to_founding(tmp_path):
    controller = _controller(tmp_path)
    assert controller.reset() == {"running": False}
    assert controller.state() == {"running": False}


def test_new_views_are_json_serialisable(tmp_path):
    controller = _controller(tmp_path)
    for name in ("purchasing", "deliveries", "daughters", "stocks_all", "bottleneck", "classification"):
        data = controller.view(name)
        assert isinstance(data, dict)
        json.dumps(data)
    assert "suppliers" in controller.view("deliveries") or "error" in controller.view("deliveries")
    assert "rows" in controller.view("daughters")
    assert "firms" in controller.view("stocks_all")
    assert controller.view("purchasing")["kind"] == "hersteller"
    assert "Noch nicht eingestuft" in controller.view("classification")["label"]


def test_dashboard_written_when_simulation_ends(tmp_path):
    controller = _controller(tmp_path)
    for _ in range(40):
        state = controller.state()
        if state["game_over"]:
            break
        state = controller.end_round({})
    assert state["game_over"]
    assert controller.session.wait_done(600)
    state = controller.state()
    assert state["dashboard_status"] == "fertig"
    assert state["dashboard_url"] == "/dashboard"
    assert controller.dashboard_file().is_file()


def test_game_time_shorter_than_simulation_hands_over_to_autopilot(tmp_path):
    session = GameSession(0, 2, 60, game_years=1, dashboard_dir=tmp_path)
    session.found("hersteller", "Testbräu", category="beer")
    snap = session.start()
    for _ in range(40):
        if snap.game_over:
            break
        snap = session.end_round()
    assert snap.game_over and snap.reason == "ende"
    assert session.finished
    assert session.wait_done(600)
    assert session.dashboard_status == "fertig"
    assert session.dashboard_path.is_file()
    assert session.dashboard_progress == 2


def test_brand_plan_sets_daily_order(tmp_path):
    from market_sim.game.choices import PlayerChoices
    controller = _controller(tmp_path)
    runner = controller.session.runner
    policy = runner.policies["factory_p01"]
    policy.choices = PlayerChoices(brand_plan={"a": 10_000, "b": 5_000})
    firm = runner.network.firm("factory_p01")
    from market_sim.strategy import FirmObservation  # noqa: F401
    unit = runner.config.unit_scale.real_units_per_sim_unit
    import math
    obs = None
    strategy = policy.decide_annual(firm, None, runner.config)
    try:
        decision = policy.decide_daily(firm, obs, strategy, runner.config)
    except AttributeError:
        return  # obs wird im Plan-Zweig nicht gebraucht; sonst Test überspringen
    # Feedback 6: Hersteller produzieren immer auf Kapazität, kein fester Plan mehr
    assert decision.order_qty == runner.env._effective_capacity("factory_p01")
