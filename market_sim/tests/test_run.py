from __future__ import annotations

import csv

from market_sim.run import main, run_simulation, write_outputs
from market_sim.runner import RunResult


def test_run_simulation_tiny_horizon():
    result = run_simulation(years=2, days_per_year=15, seed=0)
    assert isinstance(result, RunResult)
    assert len(result.annual_reports) == 2
    assert len(result.system_kpis) == 2


def test_write_outputs(tmp_path):
    result = run_simulation(years=2, days_per_year=15, seed=0)
    paths = write_outputs(result, tmp_path)
    expected_rows = {
        "annual_reports.csv": 2 * 8,
        "system_kpis.csv": 2,
        "firm_ranking.csv": 8,
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


def test_main_writes_to_requested_directory(tmp_path):
    main(["--years", "1", "--days-per-year", "10", "--out", str(tmp_path)])
    assert {path.name for path in tmp_path.iterdir()} == {
        "annual_reports.csv", "system_kpis.csv", "firm_ranking.csv",
    }
