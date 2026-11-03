from __future__ import annotations

import csv
from dataclasses import replace

import pytest

from market_sim.config import load_market_config
from market_sim.run import main, print_summary, run_simulation, write_outputs
from market_sim.runner import RunResult
from market_sim.models import load_firms


def test_run_simulation_tiny_horizon():
    result = run_simulation(years=2, days_per_year=15, seed=0)
    assert isinstance(result, RunResult)
    assert len(result.annual_reports) == 2
    assert len(result.system_kpis) == 2


def test_write_outputs(tmp_path):
    result = run_simulation(years=2, days_per_year=15, seed=0)
    firm_count = sum(len(stage.firms) for stage in result.network.stages)
    paths = write_outputs(result, tmp_path)
    expected_rows = {
        "annual_reports.csv": 2 * firm_count,
        "system_kpis.csv": 2,
        "firm_ranking.csv": firm_count,
        "events.csv": len(result.events),
    }
    assert {path.name for path in paths} == set(expected_rows)
    for path in paths:
        assert path.exists() and path.stat().st_size > 0
        with path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.reader(source))
        assert rows[0]
        assert len(rows) - 1 == expected_rows[path.name]


def test_run_simulation_is_deterministic():
    first = run_simulation(years=2, days_per_year=15, seed=0)
    second = run_simulation(years=2, days_per_year=15, seed=0)
    assert first.final_result.total_profit == second.final_result.total_profit


@pytest.mark.parametrize("enabled", [True, False])
def test_bankruptcy_exits_in_result_and_outputs(tmp_path, capsys, enabled):
    config = load_market_config()
    config = config.model_copy(update={
        "bank": config.bank.model_copy(update={"enabled": False}),
        "market_entry": config.market_entry.model_copy(update={"enabled": False}),
        "bankruptcy": config.bankruptcy.model_copy(update={
            "enabled": enabled, "cash_threshold": 1e15, "min_years_before_exit": 1,
            "min_firms_per_stage": 0, "max_exits_per_stage_per_year": 0,
        }),
    })
    result = run_simulation(years=2, days_per_year=2, seed=0, config=config)
    firm_ids = set(result.final_result.firm_results)
    assert result.exits == ({firm_id: 1 for firm_id in firm_ids} if enabled else {})

    write_outputs(result, tmp_path)
    with (tmp_path / "firm_ranking.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        assert "exit_year" in reader.fieldnames
        rows = list(reader)
    assert {row["firm"] for row in rows} == firm_ids
    assert all(row["exit_year"] == ("1" if enabled else "") for row in rows)

    print_summary(result)
    output = capsys.readouterr().out
    assert "MVP has no bankruptcy/exit" not in output
    assert ("Exited (bankrupt):" in output) == enabled
    if enabled:
        assert all(f"{firm_id} (after year 1)" in output for firm_id in firm_ids)
        assert "WARNING: negative final cash but still active:" not in output


def test_main_writes_to_requested_directory(tmp_path):
    main(["--years", "1", "--days-per-year", "10", "--out", str(tmp_path)])
    assert {path.name for path in tmp_path.iterdir()} == {
        "annual_reports.csv", "system_kpis.csv", "firm_ranking.csv", "events.csv",
    }


def test_summary_distinguishes_exits_from_active_negative_cash(capsys):
    result = run_simulation(years=0, seed=0)
    assert result.exits == {}
    exited, active = sorted(result.final_result.firm_results)[:2]
    firm_results = {
        firm_id: replace(firm, cash=-1.0 if firm_id in (exited, active) else 0.0)
        for firm_id, firm in result.final_result.firm_results.items()
    }
    result = replace(
        result, exits={exited: 1},
        final_result=replace(result.final_result, firm_results=firm_results),
    )
    print_summary(result)
    lines = capsys.readouterr().out.splitlines()
    assert f"Exited (bankrupt): {exited} (after year 1)" in lines
    assert f"WARNING: negative final cash but still active: {active}" in lines
