"""The experiment command: seed ranges, isolation of runs and the summary CSV."""

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


def test_summary_has_mean_std_min_max_per_scenario(tmp_path) -> None:
    rows, summary = run_experiment(
        [0, 1], ["basis", "nachfrage_einbruch"], fork_year=1, out=tmp_path,
        years=2, days_per_year=30,
    )
    assert len(rows) == 4
    with (tmp_path / "experiment_summary.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        table = list(reader)
    assert reader.fieldnames == ["scenario", "metric", "n", "mean", "std", "min", "max"]
    assert len(table) == 2 * (len(METRICS) + 1)
    pick = {(row["scenario"], row["metric"]): row for row in table}
    # The scenario must change the outcome. (With 30-day years and consumer classes a
    # demand cut can even raise profit, because it relieves the tight capacity.)
    assert float(pick[("nachfrage_einbruch", "total_profit")]["mean"]) != float(
        pick[("basis", "total_profit")]["mean"]
    )
    assert float(pick[("basis", "total_profit")]["min"]) <= float(pick[("basis", "total_profit")]["max"])
    assert (tmp_path / "experiment_runs.csv").exists()
    assert list((tmp_path / "checkpoints").glob("seed_*/year_01.pkl"))


def _without_runtime(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "runtime_seconds"}


def test_basis_matches_a_plain_run_and_runs_are_isolated(tmp_path) -> None:
    alone = [_without_runtime(r) for r in run_seed((1, ("basis",), 1, str(tmp_path / "a"), 2, 30))]
    together = [_without_runtime(r) for r in run_seed((1, ("nachfrage_einbruch", "basis"), 1, str(tmp_path / "b"), 2, 30))]
    assert next(r for r in together if r["scenario"] == "basis") == alone[0]
    plain = run_simulation(years=2, days_per_year=30, seed=1)
    assert alone[0]["total_profit"] == pytest.approx(plain.system_kpis[1].total_profit)
    again = [_without_runtime(r) for r in run_seed((1, ("nachfrage_einbruch",), 1, str(tmp_path / "c"), 2, 30))]
    assert again[0] == next(r for r in together if r["scenario"] == "nachfrage_einbruch")


def test_unknown_scenario_and_fork_year_are_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="unknown scenario"):
        run_experiment([0], ["gibt_es_nicht"], 1, tmp_path, years=2, days_per_year=10)
    with pytest.raises(ValueError, match="fork year"):
        run_experiment([0], ["basis"], 2, tmp_path, years=2, days_per_year=10)


def test_cli_prints_summary(tmp_path, capsys) -> None:
    main([
        "--seeds", "0-1", "--scenarios", "basis,brauerei_engpass", "--fork-year", "1",
        "--years", "2", "--days-per-year", "30", "--workers", "2", "--out", str(tmp_path),
    ])
    output = capsys.readouterr().out
    assert "brauerei_engpass" in output and "Difference to 'basis'" in output
    assert (tmp_path / "experiment_summary.csv").exists()
