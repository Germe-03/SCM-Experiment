"""Phase 7: research projects with cost, duration and an uncertain outcome."""

import pytest

from market_sim.run import build_runner


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state


def _finish(runner, state, firm_id, name, success):
    lab = runner.lab
    lab.projects[name].success_probability = 1.0 if success else 0.0
    lab.running[firm_id] = (name, 0, runner.env.period, 1000.0, 1)
    lab.year_end(runner, state)


def test_project_costs_are_booked_daily_while_running():
    runner, _ = _runner()
    env, lab = runner.env, runner.lab
    lab.running = {"retailer_01": ("prozessautomation", env.period, env.period + 5, 250.0, 1)}
    before = env.runtimes["retailer_01"].rnd_spend
    lab.daily(env)
    assert env.runtimes["retailer_01"].rnd_spend == pytest.approx(before + 250.0)


def test_successful_automation_raises_productivity():
    runner, state = _runner()
    firm = runner.network.firm("retailer_01")
    before = firm.productivity_per_employee
    _finish(runner, state, firm.id, "prozessautomation", True)
    assert firm.productivity_per_employee == pytest.approx(before * 1.15)
    assert runner.lab.reports[-1]["success"] is True


def test_failed_project_changes_nothing_but_is_reported():
    runner, state = _runner()
    firm = runner.network.firm("retailer_01")
    before = firm.productivity_per_employee
    _finish(runner, state, firm.id, "prozessautomation", False)
    assert firm.productivity_per_employee == before
    assert runner.lab.reports[-1]["success"] is False
    assert state.events[-1]["event"] in ("rnd_failure", "rnd_started")


def test_cost_reduction_lowers_material_cost_of_the_producer():
    runner, state = _runner()
    env = runner.env
    firm = runner.network.firm("factory_02")
    before = env.unit_production_cost(firm)
    _finish(runner, state, firm.id, "rezeptur_optimierung", True)
    assert env.unit_production_cost(firm) == pytest.approx(before * 0.92)


def test_alcohol_free_project_creates_a_brand_with_that_trait():
    runner, state = _runner()
    book = runner.env.brand_book
    count = len(book.brands_of("factory_01"))
    _finish(runner, state, "factory_01", "alkoholfreies_bier", True)
    own = book.brands_of("factory_01")
    assert len(own) == count + 1
    assert any("alkoholfrei" in book.brands[b].traits for b in own)
