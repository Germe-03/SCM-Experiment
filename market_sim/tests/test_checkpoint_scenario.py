from __future__ import annotations

import csv

import pytest

from market_sim.checkpoint import checkpoint_path, load_checkpoint
from market_sim.run import main as run_main, resume_simulation, run_simulation, write_outputs
from market_sim.scenario import (
    PriceShiftPolicy, get_scenario, load_scenarios, main as scenario_main, run_fork,
)

YEARS, DAYS, FORK_YEAR = 4, 20, 2


def _reports(result):
    return [{key: value.model_dump() for key, value in year.items()} for year in result.annual_reports]


def _kpis(result):
    return [kpi.model_dump() for kpi in result.system_kpis]


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    directory = tmp_path_factory.mktemp("baseline")
    result = run_simulation(
        years=YEARS, days_per_year=DAYS, seed=0, checkpoint_dir=directory / "checkpoints",
    )
    write_outputs(result, directory)
    return directory, result


def test_one_checkpoint_per_year(baseline):
    directory, _ = baseline
    assert sorted(path.name for path in (directory / "checkpoints").iterdir()) == [
        f"year_{year:02d}.pkl" for year in range(1, YEARS + 1)
    ]
    _, state = load_checkpoint(checkpoint_path(directory / "checkpoints", FORK_YEAR))
    assert state.year == FORK_YEAR and len(state.annual_reports) == FORK_YEAR


def test_resume_matches_uninterrupted_run(baseline):
    directory, straight = baseline
    resumed = resume_simulation(checkpoint_path(directory / "checkpoints", FORK_YEAR))
    assert _reports(resumed) == _reports(straight)
    assert _kpis(resumed) == _kpis(straight)
    assert resumed.exits == straight.exits
    assert resumed.days_total == straight.days_total
    assert {key: value.cash for key, value in resumed.final_result.firm_results.items()} == {
        key: value.cash for key, value in straight.final_result.firm_results.items()
    }


def test_checkpoints_do_not_change_results(baseline):
    _, with_checkpoints = baseline
    plain = run_simulation(years=YEARS, days_per_year=DAYS, seed=0)
    assert _reports(plain) == _reports(with_checkpoints)


@pytest.mark.parametrize("name", sorted(load_scenarios()))
def test_scenario_changes_only_years_after_fork(baseline, name):
    directory, straight = baseline
    fork = run_fork(checkpoint_path(directory / "checkpoints", FORK_YEAR), get_scenario(name))
    assert _reports(fork)[:FORK_YEAR] == _reports(straight)[:FORK_YEAR]
    assert _reports(fork)[FORK_YEAR:] != _reports(straight)[FORK_YEAR:]


def test_scenario_effects_point_the_right_way(baseline):
    directory, straight = baseline
    checkpoint = checkpoint_path(directory / "checkpoints", FORK_YEAR)
    runner, _ = load_checkpoint(checkpoint)
    factories = [firm.id for firm in runner.network.firms_in("factory")]

    def factory_price(result):
        return sum(result.annual_reports[-1][firm].average_sell_price for firm in factories)

    pricier = run_fork(checkpoint, get_scenario("preiserhoehung_brauerei"))
    assert factory_price(pricier) > factory_price(straight)
    weaker = run_fork(checkpoint, get_scenario("nachfrage_einbruch"))
    assert sum(weaker.annual_reports[-1][firm].revenue for firm in factories) < sum(
        straight.annual_reports[-1][firm].revenue for firm in factories
    )


def test_price_shift_stays_inside_stage_band(baseline):
    directory, _ = baseline
    runner, _ = load_checkpoint(checkpoint_path(directory / "checkpoints", FORK_YEAR))
    firm = runner.network.firms_in("factory")[0]
    strategy = PriceShiftPolicy(runner.policies[firm.id], 10.0).decide_annual(firm, None, runner.config)
    assert strategy.max_price == runner.config.stage_prices["factory"].max


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError, match="unknown scenario"):
        get_scenario("gibt_es_nicht")


def test_cli_fork_writes_comparison(baseline, tmp_path, capsys):
    directory, _ = baseline
    scenario_main([
        "--from", str(checkpoint_path(directory / "checkpoints", FORK_YEAR)),
        "--scenario", "brauerei_engpass", "--out", str(tmp_path), "--baseline", str(directory),
    ])
    with (tmp_path / "comparison.csv").open(newline="", encoding="utf-8") as source:
        years = list(csv.DictReader(source))
    assert [int(row["year"]) for row in years] == list(range(1, YEARS + 1))
    assert all(float(row["total_profit_diff"]) == 0 for row in years[:FORK_YEAR])
    with (tmp_path / "firm_comparison.csv").open(newline="", encoding="utf-8") as source:
        assert {"cumulative_profit_diff", "exit_year_scenario"} <= set(csv.DictReader(source).fieldnames)
    assert "Scenario vs. baseline" in capsys.readouterr().out


def test_cli_checkpoints_and_resume(tmp_path):
    run_main([
        "--years", "2", "--days-per-year", "10", "--out", str(tmp_path / "a"), "--checkpoints",
    ])
    assert (tmp_path / "a" / "checkpoints" / "year_02.pkl").exists()
    run_main(["--resume", str(tmp_path / "a" / "checkpoints" / "year_01.pkl"), "--out", str(tmp_path / "b")])
    with (tmp_path / "a" / "system_kpis.csv").open(encoding="utf-8") as first, \
            (tmp_path / "b" / "system_kpis.csv").open(encoding="utf-8") as second:
        assert first.read() == second.read()
