"""Phase 25: patents for the first researcher; others may research but not implement."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state


def _finish(runner, state, firm_id, name, step, success=True, tree="factory"):
    lab = runner.lab
    lab.stages[tree][name].success_probability = 1.0 if success else 0.0
    lab.running[firm_id] = (name, 0, runner.env.period, 1000.0, 1, step, tree)
    lab.year_end(runner, state)


def test_first_researcher_gets_patent_and_pays_fee():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    runner.env.runtimes[a].cash = 1e12
    cash_before = runner.env.runtimes[a].cash

    _finish(runner, state, a, "mehrwegsystem", "research")

    office = runner.patent_office
    patent = office.active[("factory", "mehrwegsystem")]
    assert office.holder("factory", "mehrwegsystem") == a
    assert any(
        event["firm"] == a and event["event"] == "patent_granted"
        for event in state.events
    )
    fee_cash_flow = runner.env.runtimes[a].cash_flows["staat:Patentgebühr"]
    assert fee_cash_flow < 0
    assert fee_cash_flow == pytest.approx(-patent["fee"])
    assert runner.env.runtimes[a].cash < cash_before
    assert patent["years"] == 5
    assert patent["expires_year"] == patent["granted_year"] + 5
    assert office.stats["patents_granted"] == 1


def test_not_patentable_and_second_researcher():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12
    runner.env.runtimes[b].cash = 1e12

    _finish(runner, state, a, "leichtere_flaschen", "research")
    assert ("factory", "leichtere_flaschen") not in runner.patent_office.active

    _finish(runner, state, a, "mehrwegsystem", "research")
    _finish(runner, state, b, "mehrwegsystem", "research")

    assert runner.patent_office.holder("factory", "mehrwegsystem") == a
    assert len(runner.patent_office.active) == 1
    assert runner.lab.progress[b]["mehrwegsystem"] == "researched"


def test_choose_years():
    runner, _ = _runner()
    runner.lab.cfg.start_probability = 0.0
    office = runner.patent_office

    assert office.choose_years(SimpleNamespace(archetype="premium"), 0.0, 1.0) == 5
    assert office.choose_years(SimpleNamespace(archetype="low_cost"), 0.0, 1.0) == 3
    assert office.choose_years(SimpleNamespace(archetype="standard"), 0.0, 1.0) == 4
    assert office.choose_years(SimpleNamespace(archetype="standard"), 1e12, 1.0) == 5
    assert office.fee(3, 1.0) == 5_000_000
    assert office.fee(5, 2.0) == 14_000_000


def test_patent_blocks_implementation_of_others():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12
    runner.env.runtimes[b].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    lab = runner.lab
    lab.progress[b] = {
        "leichtere_flaschen": "implemented",
        "mehrwegsystem": "researched",
    }
    state.summaries[-1][b] = replace(state.summaries[-1][b], profit=1e6)
    lab.running.pop(b, None)

    lab.year_end(runner, state)

    assert b not in lab.running or lab.running[b][5] != "implementation" or lab.running[b][0] != "mehrwegsystem"
    assert runner.patent_office.blocked(b, "factory", "mehrwegsystem") is True
    assert runner.patent_office.blocked(a, "factory", "mehrwegsystem") is False


def test_prior_user_may_continue():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12
    runner.lab.running[b] = (
        "mehrwegsystem",
        0,
        10**6,
        1.0,
        1,
        "implementation",
        "factory",
    )

    _finish(runner, state, a, "mehrwegsystem", "research")

    patent = runner.patent_office.active[("factory", "mehrwegsystem")]
    assert b in patent["prior_users"]
    assert runner.patent_office.blocked(b, "factory", "mehrwegsystem") is False


def test_expiry_unblocks():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    office = runner.patent_office
    patent = office.active[("factory", "mehrwegsystem")]
    patent["expires_year"] = state.year
    office.year_end(runner, state)

    assert ("factory", "mehrwegsystem") not in office.active
    assert patent["status"] == "expired"
    assert any(
        event["firm"] == a and event["event"] == "patent_expired"
        for event in state.events
    )
    assert office.blocked(b, "factory", "mehrwegsystem") is False


def test_bankruptcy_lapses_patent():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    runner.env.runtimes[a].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    office = runner.patent_office
    patent = office.active[("factory", "mehrwegsystem")]
    runner.env.runtimes[a].active = False
    office.year_end(runner, state)

    assert ("factory", "mehrwegsystem") not in office.active
    assert patent["status"] == "lapsed"


def test_takeover_moves_patent():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    b = next(
        firm_id
        for firm_id in [f.id for f in runner.network.firms_in("factory")]
        if firm_id != a
    )
    runner.env.runtimes[a].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    runner.patent_office.transfer(a, b, 1)

    assert runner.patent_office.holder("factory", "mehrwegsystem") == b
    assert runner.patent_office.active[("factory", "mehrwegsystem")]["first_holder"] == a


def test_report_and_disabled():
    runner, state = _runner()
    runner.lab.cfg.start_probability = 0.0
    a = "factory_01"
    runner.env.runtimes[a].cash = 1e12

    _finish(runner, state, a, "mehrwegsystem", "research")

    office = runner.patent_office
    report = office.report()
    assert len(report) == 1
    assert {"tree", "stage", "holder", "years", "fee", "status"} <= report[0].keys()
    report[0]["holder"] = "changed"
    assert office.history[0]["holder"] == a

    config = load_market_config()
    config.patents.enabled = False
    disabled_runner, _ = build_runner(1, 0, days_per_year=10, config=config)
    assert disabled_runner.patent_office is None


def test_stock_shock_configured():
    runner, _ = _runner()
    runner.lab.cfg.start_probability = 0.0

    assert runner.config.stock_market.event_shocks["patent_granted"] > 0
