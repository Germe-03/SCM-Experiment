from __future__ import annotations

import pytest

from market_sim.checkpoint import checkpoint_path, load_checkpoint
from market_sim.run import main as run_main, resume_simulation, run_simulation, write_outputs

YEARS, DAYS, RESUME_YEAR = 4, 20, 2


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
    _, state = load_checkpoint(checkpoint_path(directory / "checkpoints", RESUME_YEAR))
    assert state.year == RESUME_YEAR and len(state.annual_reports) == RESUME_YEAR


def test_resume_matches_uninterrupted_run(baseline):
    directory, straight = baseline
    resumed = resume_simulation(checkpoint_path(directory / "checkpoints", RESUME_YEAR))
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


def test_cli_checkpoints_and_resume(tmp_path):
    run_main([
        "--years", "2", "--days-per-year", "10", "--out", str(tmp_path / "a"), "--checkpoints",
    ])
    assert (tmp_path / "a" / "checkpoints" / "year_02.pkl").exists()
    run_main(["--resume", str(tmp_path / "a" / "checkpoints" / "year_01.pkl"), "--out", str(tmp_path / "b")])
    with (tmp_path / "a" / "system_kpis.csv").open(encoding="utf-8") as first, \
            (tmp_path / "b" / "system_kpis.csv").open(encoding="utf-8") as second:
        assert first.read() == second.read()
