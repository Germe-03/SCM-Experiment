"""Realised savings and verdict accounting, including uncaught offences."""

import csv

import pytest

from market_sim.run import build_runner, write_outputs


@pytest.mark.parametrize("kind", ["wage", "material", "tax"])
@pytest.mark.parametrize("caught", [False, True])
def test_ledger_gain_fine_damage_and_verdict(kind, caught):
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    actor, env = runner.state_actor, runner.env
    firm = runner.network.firm("factory_01")
    offence = next(o for o in actor.cfg.offences if o.kind == kind)
    offence.detection_probability = float(caught)
    actor.cfg.poisoning_probability = 0
    actor.active = {firm.id: {offence.name}}
    actor.previous_revenue[firm.id] = 200e6
    env.wage_savings[firm.id] = 1234
    env.material_savings[firm.id] = 5678
    actor.year_end(runner, state)
    row = actor.offence_ledger[-1]
    expected_gain = {"wage": 1234, "material": 5678, "tax": max(0, state.summaries[-1][firm.id].profit) * actor.cfg.profit_tax * offence.benefit}[kind]
    assert row["gain"] == pytest.approx(expected_gain)
    assert row["fine"] == pytest.approx(offence.fine_fixed * runner.long_run.price_index + offence.fine_revenue_share * state.summaries[-1][firm.id].revenue if caught else 0)
    assert row["damage"] == pytest.approx(offence.reputation_hit * 200e6 * 0.5 if caught else 0)
    assert row["net"] == pytest.approx(row["gain"] - row["fine"] - row["damage"])
    assert row["paid_off"] == (row["net"] > 0)


def test_material_savings_count_produced_units_only():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    env, firm = runner.env, runner.network.firm("factory_01")
    base = env.unit_production_cost(firm)
    env.firm_material_factor[firm.id] = 0.9
    env.unit_production_cost(firm)
    assert not env.material_savings
    assert env.unit_production_cost(firm, 123) == pytest.approx(base * 0.9)
    assert env.material_savings[firm.id] == pytest.approx(123 * base * 0.1)


def test_actual_wage_savings_and_ledger_export(tmp_path):
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    actor, env = runner.state_actor, runner.env
    rt = env.runtimes["retailer_01"]
    rt.wage_cost_last_year = 1e9
    actor.beliefs["retailer_01"]["lohndumping"] = [0, 0]
    result = runner.continue_run(state, 1)
    row = next(r for r in result.offence_ledger if r["firm"] == "retailer_01" and r["offence"] == "lohndumping")
    assert row["gain"] == pytest.approx(rt.wage_cost * 0.08 / 0.92)
    write_outputs(result, tmp_path)
    with (tmp_path / "offence_ledger.csv").open(encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(result.offence_ledger)
