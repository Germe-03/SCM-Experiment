import json

import pytest

from market_sim.game.change_log import describe_changes
from market_sim.game.controller import GameController


def make(path, years=2):
    return GameController(path, seed=0, years=years, days_per_year=60)


def start(controller):
    state = controller.new_game("hersteller", "Testbrauerei")
    assert "error" not in state, state
    return state


def test_autosave_after_new_game_and_end_round(tmp_path):
    controller = make(tmp_path)
    start(controller)
    assert (tmp_path / "automatisch.json").exists()
    state = controller.end_round({})
    assert "error" not in state
    assert (tmp_path / "automatisch_vorher.json").exists()
    assert state["autosaved_at"]


def test_second_controller_loads_autosave(tmp_path):
    controller = make(tmp_path)
    start(controller)
    state = controller.end_round({})
    other = make(tmp_path)
    loaded = other.load("automatisch")
    assert "error" not in loaded, loaded
    assert (loaded["year"], loaded["month"]) == (state["year"], state["month"])


def test_reset_creates_backup(tmp_path):
    controller = make(tmp_path)
    start(controller)
    assert controller.reset() == {"running": False}
    assert (tmp_path / "vor_neuem_spiel.json").exists()


def test_autosave_never_raises(tmp_path):
    controller = make(tmp_path)
    start(controller)
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    controller.save_dir = blocker / "unterordner"  # nicht anlegbar
    controller._autosave()


def test_loading_state(tmp_path):
    controller = make(tmp_path)
    controller.loading = True
    assert controller.state() == {"running": False, "loading": True}


def test_no_game_error(tmp_path):
    controller = make(tmp_path)
    assert controller.end_round({})["error"] == "Kein Spiel aktiv – Seite neu laden"


def test_run_to_end(tmp_path):
    controller = make(tmp_path)
    start(controller)
    state = controller.run_to_end({}, {}, {})
    assert "error" not in state, state
    assert state["game_over"] is True
    assert state["end_reason_text"] == "Du hast bis zum Ende simuliert."
    assert controller.session.wait_done(300)


def test_describe_changes_dict_readable():
    plan = {f"Marke{i}": 1000 * (i + 1) for i in range(7)}
    lines = describe_changes(None, {}, {"brand_plan": plan, "listing": False}, {})
    assert lines[0].startswith("Einkaufsplan geändert: Marke0 1'000")
    assert "und 2 weitere" in lines[0]
    assert "{" not in lines[0]
    assert "Nein (Standard)" in lines[1]


def test_demand_not_below_sales(tmp_path):
    controller = make(tmp_path)
    state = start(controller)
    for _ in range(3):
        state = controller.end_round({})
        assert state["kpis"]["recent_demand"] >= state["kpis"]["recent_sales"]
