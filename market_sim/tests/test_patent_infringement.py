"""Phase 26: patent infringement as an offence (fine, compensation, effect undone)."""

import random
from dataclasses import replace

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    runner.lab.cfg.start_probability = 0.0
    return runner, state


def _finish(runner, state, firm_id, name, step, success=True, tree="factory"):
    lab = runner.lab
    lab.stages[tree][name].success_probability = 1.0 if success else 0.0
    lab.running[firm_id] = (name, 0, runner.env.period, 1000.0, 1, step, tree)
    lab.year_end(runner, state)


def _setup(willing=True):
    runner, state = _runner()
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12
    runner.env.runtimes[b].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    runner.state_actor.willing = lambda firm_id: willing
    office = runner.patent_office
    office.cfg.infringement.advantage_per_effect = 100.0
    runner.env.runtimes[b].last_year_revenue = 1e9

    lab = runner.lab
    lab.progress[b] = {
        "leichtere_flaschen": "implemented",
        "mehrwegsystem": "researched",
    }
    state.summaries[-1][b] = replace(state.summaries[-1][b], profit=1e6)
    lab.running.pop(b, None)
    return runner, state, a, b


def _start_and_implement(runner, state, b):
    runner.lab.year_end(runner, state)
    assert runner.lab.running[b][0] == "mehrwegsystem"
    assert runner.lab.running[b][5] == "implementation"

    before = runner.env.component_factor.get(b, {}).get("packaging", 1.0)
    runner.lab.running[b] = (
        "mehrwegsystem",
        0,
        runner.env.period,
        1000.0,
        1,
        "implementation",
        "factory",
    )
    runner.lab.year_end(runner, state)
    return before


def test_unwilling_firm_never_infringes():
    runner, state, _, b = _setup(willing=False)
    office = runner.patent_office
    lab = runner.lab

    lab.year_end(runner, state)

    assert (b, "factory", "mehrwegsystem") not in office.infringements
    assert b not in lab.running or lab.running[b][0] != "mehrwegsystem"
    assert office.consider_infringement(
        runner,
        state,
        runner.network.firm(b),
        "factory",
        lab.stages["factory"]["mehrwegsystem"],
    ) is False


def test_disabled_never_infringes_and_draws_nothing():
    runner, state, _, b = _setup()
    office = runner.patent_office
    office.cfg.infringement.enabled = False
    rng_state = office.rng.getstate()

    runner.lab.year_end(runner, state)

    assert (b, "factory", "mehrwegsystem") not in office.infringements
    assert office.consider_infringement(
        runner,
        state,
        runner.network.firm(b),
        "factory",
        runner.lab.stages["factory"]["mehrwegsystem"],
    ) is False
    assert office.rng.getstate() == rng_state


def test_willing_firm_infringes_and_implements():
    runner, state, _, b = _setup()
    before = _start_and_implement(runner, state, b)
    key = (b, "factory", "mehrwegsystem")

    assert runner.patent_office.infringements[key]["status"] == "active"
    assert runner.lab.progress[b]["mehrwegsystem"] == "implemented"
    assert runner.env.component_factor[b]["packaging"] == pytest.approx(before * 0.8)
    if runner.decision_log.enabled:
        assert any(
            entry["firm"] == b
            and entry["decision"] == "offence"
            and entry["value"]["offence"] == "patentverletzung"
            and entry["value"]["committed"]
            for entry in runner.decision_log.entries
        )


def test_detection_fines_compensates_and_undoes():
    runner, state, a, b = _setup()
    before = _start_and_implement(runner, state, b)
    office = runner.patent_office
    office.cfg.infringement.detection_probability = 1.0
    rep_before = runner.network.firm(b).reputation
    cash_a = runner.env.runtimes[a].cash
    key = (b, "factory", "mehrwegsystem")
    office.infringements[key]["active_year"] = state.year - 1

    office.year_end(runner, state)

    assert key not in office.infringements
    assert office.infringement_history[-1]["status"] == "caught"
    runtime_b = runner.env.runtimes[b]
    runtime_a = runner.env.runtimes[a]
    assert runtime_b.cash_flows["staat:Busse patentverletzung"] < 0
    compensation_paid = runtime_b.cash_flows[f"schadenersatz:{a}"]
    assert compensation_paid < 0
    assert runtime_a.cash_flows[f"schadenersatz:{b}"] == pytest.approx(-compensation_paid)
    assert -compensation_paid >= (
        office.cfg.infringement.min_damages * runner.long_run.price_index * 0.999
    )
    assert runtime_a.cash > cash_a
    assert runner.network.firm(b).reputation == pytest.approx(max(0.0, rep_before - 0.05))
    assert runner.env.component_factor[b]["packaging"] == pytest.approx(before)
    assert runner.lab.progress[b]["mehrwegsystem"] == "researched"
    assert any(
        event["firm"] == b
        and event["event"] == "offence_detected"
        and "Patentverletzung" in event["details"]
        for event in state.events
    )

    rows = [
        row
        for row in runner.state_actor.offence_ledger
        if row["offence"] == "patentverletzung"
    ]
    assert len(rows) == 1
    assert rows[0]["firm"] == b
    assert rows[0]["holder"] == a
    assert rows[0]["fine"] > 0
    assert rows[0]["compensation"] > 0
    assert rows[0]["net"] == pytest.approx(
        rows[0]["gain"]
        - rows[0]["fine"]
        - rows[0]["damage"]
        - rows[0]["compensation"]
    )
    assert len(office.ledger) == 1


def test_undetected_until_expiry_ends_unpunished():
    runner, state, _, b = _setup()
    before = _start_and_implement(runner, state, b)
    office = runner.patent_office
    office.cfg.infringement.detection_probability = 0.0
    key = (b, "factory", "mehrwegsystem")
    office.infringements[key]["active_year"] = state.year - 1

    office.year_end(runner, state)

    assert office.infringements[key]["status"] == "active"
    assert len(office.ledger) == 1
    assert office.ledger[0]["fine"] == 0
    assert office.ledger[0]["compensation"] == 0

    office.active[("factory", "mehrwegsystem")]["expires_year"] = state.year
    office.year_end(runner, state)

    assert key not in office.infringements
    assert office.infringement_history[-1]["status"] == "ended"
    assert runner.env.component_factor[b]["packaging"] == pytest.approx(before * 0.8)
    assert runner.lab.progress[b]["mehrwegsystem"] == "implemented"
    assert runner.env.runtimes[b].cash_flows.get(
        "staat:Busse patentverletzung", 0.0
    ) == 0.0


def test_undo_productivity_and_robotics():
    runner, _ = _runner()
    lab = runner.lab
    firm = runner.network.firm("factory_01")
    stage = lab.stages["factory"]["smart_factory"]
    productivity = firm.productivity_per_employee

    lab._apply_stage(runner, firm, stage)

    assert firm.productivity_per_employee != productivity
    lab.progress.setdefault(firm.id, {})["smart_factory"] = "implemented"
    lab.undo_stage(runner, firm, stage, {})

    assert firm.productivity_per_employee == pytest.approx(productivity)
    assert lab.progress[firm.id]["smart_factory"] == "researched"

    wholesaler = runner.network.firms_in("wholesaler")[0]
    stage = lab.stages["wholesaler"]["kommissionier_roboter"]
    employees_before = wholesaler.employees
    productivity_before = wholesaler.productivity_per_employee

    lab._apply_stage(runner, wholesaler, stage)
    record = {
        "employees_before": employees_before,
        "employees_after": wholesaler.employees,
    }
    lab.undo_stage(runner, wholesaler, stage, record)

    assert wholesaler.employees == employees_before
    assert runner.env.runtimes[wholesaler.id].employees == employees_before
    assert wholesaler.productivity_per_employee == pytest.approx(productivity_before)


def test_determinism():
    def run():
        runner, _ = build_runner(2, 0, days_per_year=10)
        state = runner.start()
        runner.continue_run(state, 2)
        if hasattr(state, "annual_reports"):
            reports = [
                {key: value.model_dump() for key, value in year.items()}
                for year in state.annual_reports
            ]
        else:
            reports = [sorted(summary.keys()) for summary in state.summaries]
        return list(runner.state_actor.offence_ledger), reports

    assert run() == run()

    config = load_market_config()
    config.patents.infringement.enabled = False
    runner, _ = build_runner(2, 0, days_per_year=10, config=config)
    state = runner.start()
    runner.continue_run(state, 2)

    assert runner.patent_office.rng.getstate() == random.Random(
        "patent-infringement-0"
    ).getstate()
