"""The experiment command: seed ranges, isolated runs and the summary CSV."""

import csv

import pytest

from market_sim.experiment import METRICS, main, parse_seeds, run_experiment, run_seed
from market_sim.run import run_simulation


def test_parse_seeds() -> None:
    assert parse_seeds("0-3,7") == [0, 1, 2, 3, 7]
    assert parse_seeds("5") == [5]
    assert parse_seeds("2,2,1") == [1, 2]
    with pytest.raises(ValueError):
        parse_seeds("4-2")


def test_summary_has_mean_std_min_max_per_metric(tmp_path) -> None:
    rows, summary = run_experiment([0, 1], tmp_path, skip_years=1, years=2, days_per_year=30)
    assert len(rows) == 2
    with (tmp_path / "experiment_summary.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        table = list(reader)
    assert reader.fieldnames == ["metric", "n", "mean", "std", "min", "max"]
    assert len(table) == len(METRICS) + 1
    profit = next(row for row in table if row["metric"] == "total_profit")
    assert float(profit["min"]) <= float(profit["mean"]) <= float(profit["max"])
    assert (tmp_path / "seed_00" / "annual_reports.csv").exists()


def test_seed_run_matches_a_plain_run() -> None:
    row = run_seed((1, 0, "runs/pytest-experiment", 2, 30))
    plain = run_simulation(years=2, days_per_year=30, seed=1)
    assert row["total_profit"] == pytest.approx(sum(k.total_profit for k in plain.system_kpis))


def test_skip_years_is_checked(tmp_path) -> None:
    with pytest.raises(ValueError, match="skip years"):
        run_experiment([0], tmp_path, skip_years=2, years=2, days_per_year=10)


def test_cli_prints_summary(tmp_path, capsys) -> None:
    main(["--seeds", "0-1", "--years", "2", "--days-per-year", "30", "--workers", "2", "--out", str(tmp_path)])
    output = capsys.readouterr().out
    assert "Experiment: 2 seeds" in output
    assert (tmp_path / "experiment_summary.csv").exists()
