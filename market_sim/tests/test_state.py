"""Phase 6: taxes, offences with hidden fines, poisoning, takeovers and antitrust."""

import pytest

from market_sim.run import build_runner
from market_sim.runner import YearSummary


def _runner(days=10, years=1):
    runner, _ = build_runner(years, 0, days_per_year=days)
    state = runner.start()
    runner.continue_run(state, years)
    return runner, state


def test_firm_offends_only_when_its_guess_makes_it_pay():
    runner, state = _runner()
    actor = runner.state_actor
    firm = runner.network.firm("retailer_01")
    runtime = runner.env.runtimes[firm.id]
    runtime.wage_cost_last_year = 1e9
    runtime.last_year_revenue = 1e9
    actor.beliefs[firm.id]["lohndumping"] = [0.0, 0.0]
    actor.apply_offences(runner)
    assert "lohndumping" in actor.active.get(firm.id, set())
    actor.beliefs[firm.id]["lohndumping"] = [0.99, 1.0]
    actor.apply_offences(runner)
    assert "lohndumping" not in actor.active.get(firm.id, set())


def test_detected_offence_costs_a_fine_reputation_and_teaches_the_firm():
    runner, state = _runner()
    actor = runner.state_actor
    offence = next(o for o in runner.config.state.offences if o.name == "lohndumping")
    offence.detection_probability = 1.0
    firm = runner.network.firm("retailer_01")
    actor.active = {firm.id: {"lohndumping"}}
    actor.beliefs[firm.id]["lohndumping"][0] = 0.0
    cash, reputation = runner.env.runtimes[firm.id].cash, firm.reputation
    actor.year_end(runner, state)
    assert runner.env.runtimes[firm.id].cash < cash
    assert firm.reputation < reputation
    assert actor.beliefs[firm.id]["lohndumping"][0] > 0.0
    assert any(e["event"] == "offence_detected" for e in state.events)


def test_poisoning_closes_the_producer_and_scares_consumers():
    runner, state = _runner()
    actor = runner.state_actor
    firm = runner.network.firm("winery_02")
    persons = sum(c.persons for c in runner.config.consumers.classes)
    actor._poisoning(runner, state, firm, 1, 10)
    assert not runner.env.runtimes[firm.id].active
    assert actor.fear["wine"] == pytest.approx(runner.config.state.fear_strength)
    assert sum(c.persons for c in runner.config.consumers.classes) < persons
    book = runner.env.brand_book
    book.fear = dict(actor.fear)
    requested, sold, lost = book.fulfill(runner.env, 1000)
    assert sum(sold.values()) + lost < 1000


def _summaries(runner, revenue):
    return {f.id: YearSummary(revenue=revenue.get(f.id, 1.0), profit=1.0, avg_inventory=0, avg_backlog=0,
                              lost_sales=0, service_level=1, avg_sell_price=1, quality=0.5,
                              capacity_utilization=0.5, cash=0)
            for s in runner.network.stages for f in s.firms}


def test_takeover_merges_and_antitrust_blocks_dominant_buyers():
    runner, state = _runner()
    env, actor = runner.env, runner.state_actor
    target, buyer = runner.network.firm("wholesaler_02"), runner.network.firm("wholesaler_01")
    env.runtimes[target.id].consecutive_loss_years = 5
    env.runtimes[buyer.id].cash = 1e12
    state.summaries.append(_summaries(runner, {}))
    capacity = buyer.capacity + target.capacity
    actor.takeovers(runner, state)
    assert not env.runtimes[target.id].active and buyer.capacity == capacity
    assert any(e["event"] == "takeover" for e in state.events)
    runner.config.state.block_share = 0.0
    other = runner.network.firm("wholesaler_03")
    env.runtimes[other.id].consecutive_loss_years = 5
    actor.takeovers(runner, state)
    assert env.runtimes[other.id].active
    assert any(e["event"] == "takeover_blocked" for e in state.events)


def test_dominant_firm_must_sell_a_site():
    runner, state = _runner()
    actor = runner.state_actor
    firm = runner.network.firm("retailer_01")
    firm.extra_regions.append("tessin")
    active = [f for f in runner.network.firms_in("retailer")]
    actor._break_up(runner, state, "retailer", active, {firm.id: 0.9}, 1, 10)
    assert "tessin" not in firm.extra_regions
    spin = [e for e in state.events if e["event"] == "spin_off"]
    assert spin and runner.network.firm(spin[-1]["firm"]).region == "tessin"
