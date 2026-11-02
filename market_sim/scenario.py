"""What-if forks: load a year-end checkpoint, apply a scenario, run to the end.

Example::

    python -m market_sim.run --seed 0 --out runs/base --checkpoints
    python -m market_sim.scenario --from runs/base/checkpoints/year_05.pkl \
        --scenario nachfrage_einbruch --out runs/fork_nachfrage --baseline runs/base
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Literal, TYPE_CHECKING

import yaml
from pydantic import Field, model_validator

from market_sim.checkpoint import load_checkpoint
from market_sim.config import ConfigModel, MarketConfig
from market_sim.models import STAGES, Firm
from market_sim.policies import FirmPolicy
from market_sim.run import print_summary, write_outputs
from market_sim.runner import RunResult, SimulationRunner
from market_sim.strategy import AnnualStrategy, DailyDecision, FirmObservation

if TYPE_CHECKING:
    from market_sim.runner import YearSummary

SCENARIO_PATH = Path(__file__).resolve().parent / "config" / "scenarios.yaml"
COMPARED_KPIS = (
    "total_profit", "total_lost_sales", "average_customer_price", "market_concentration",
)


class ScenarioChange(ConfigModel):
    kind: Literal["demand", "capacity", "price"]
    factor: float = Field(gt=0)
    stage: str | None = None

    @model_validator(mode="after")
    def _stage_matches_kind(self) -> "ScenarioChange":
        if self.kind == "demand" and self.stage is not None:
            raise ValueError("demand changes apply to the whole market and take no stage")
        if self.kind != "demand" and self.stage not in STAGES:
            raise ValueError(f"{self.kind} changes need a stage out of {STAGES}")
        return self


class Scenario(ConfigModel):
    name: str
    description: str
    changes: list[ScenarioChange] = Field(min_length=1)


def load_scenarios(path: str | Path | None = None) -> dict[str, Scenario]:
    with Path(path or SCENARIO_PATH).open(encoding="utf-8") as source:
        raw = yaml.safe_load(source) or {}
    return {name: Scenario(name=name, **body) for name, body in raw.items()}


def get_scenario(name: str, path: str | Path | None = None) -> Scenario:
    scenarios = load_scenarios(path)
    if name not in scenarios:
        raise ValueError(f"unknown scenario {name!r}; available: {', '.join(sorted(scenarios))}")
    return scenarios[name]


class PriceShiftPolicy:
    """Wrap a policy and scale its annual price band inside the stage band."""

    def __init__(self, inner: FirmPolicy, factor: float) -> None:
        self.inner = inner
        self.factor = factor

    def decide_annual(
        self, firm: Firm, last_summary: "YearSummary | None", config: MarketConfig,
    ) -> AnnualStrategy:
        strategy = self.inner.decide_annual(firm, last_summary, config)
        band = config.stage_prices[firm.stage]
        low, base, high = (
            max(band.min, min(band.max, value * self.factor))
            for value in (strategy.min_price, strategy.base_price, strategy.max_price)
        )
        return strategy.model_copy(update={"min_price": low, "base_price": base, "max_price": high})

    def decide_daily(
        self, firm: Firm, obs: FirmObservation, strategy: AnnualStrategy, config: MarketConfig,
    ) -> DailyDecision:
        return self.inner.decide_daily(firm, obs, strategy, config)


def apply_scenario(runner: SimulationRunner, scenario: Scenario) -> None:
    """Change the loaded market in place; effective from the next simulated day."""
    for change in scenario.changes:
        if change.kind == "demand":
            runner.demand.mean = max(0, round(runner.demand.mean * change.factor))
            continue
        for firm in runner.network.firms_in(change.stage):
            if change.kind == "capacity":
                firm.capacity = max(0, round(firm.capacity * change.factor))
                firm.machine_capacity = max(0, round(firm.machine_capacity * change.factor))
                firm.productivity_per_employee *= change.factor
            else:
                runner.policies[firm.id] = PriceShiftPolicy(runner.policies[firm.id], change.factor)


def run_fork(checkpoint: str | Path, scenario: Scenario) -> RunResult:
    runner, state = load_checkpoint(checkpoint)
    apply_scenario(runner, scenario)
    return runner.continue_run(state, runner.config.simulation.years)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def write_comparison(baseline_dir: str | Path, fork_dir: str | Path, out_dir: str | Path) -> list[Path]:
    """Compare the baseline run's CSVs with the fork's CSVs, year by year and firm by firm."""
    baseline_dir, fork_dir, out_dir = Path(baseline_dir), Path(fork_dir), Path(out_dir)
    base_years = {row["year"]: row for row in _read_csv(baseline_dir / "system_kpis.csv")}
    rows = []
    for fork_row in _read_csv(fork_dir / "system_kpis.csv"):
        base_row = base_years.get(fork_row["year"])
        if base_row is None:
            continue
        row: dict[str, object] = {"year": int(fork_row["year"])}
        for key in COMPARED_KPIS:
            base, fork = float(base_row[key]), float(fork_row[key])
            row |= {f"{key}_base": base, f"{key}_scenario": fork, f"{key}_diff": fork - base}
        rows.append(row)
    comparison = out_dir / "comparison.csv"
    with comparison.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else ["year"])
        writer.writeheader()
        writer.writerows(rows)

    base_firms = {row["firm"]: row for row in _read_csv(baseline_dir / "firm_ranking.csv")}
    firm_rows = []
    for fork_row in _read_csv(fork_dir / "firm_ranking.csv"):
        base_row = base_firms[fork_row["firm"]]
        base, fork = float(base_row["cumulative_profit"]), float(fork_row["cumulative_profit"])
        firm_rows.append({
            "firm": fork_row["firm"], "stage": fork_row["stage"], "archetype": fork_row["archetype"],
            "cumulative_profit_base": base, "cumulative_profit_scenario": fork,
            "cumulative_profit_diff": fork - base,
            "exit_year_base": base_row.get("exit_year", ""), "exit_year_scenario": fork_row["exit_year"],
        })
    firm_rows.sort(key=lambda row: row["cumulative_profit_diff"])
    firm_comparison = out_dir / "firm_comparison.csv"
    with firm_comparison.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(firm_rows[0]) if firm_rows else ["firm"])
        writer.writeheader()
        writer.writerows(firm_rows)
    return [comparison, firm_comparison]


def _print_comparison(comparison: Path, firm_comparison: Path) -> None:
    years = _read_csv(comparison)
    firms = _read_csv(firm_comparison)
    print("\nScenario vs. baseline (total profit per year)")
    for row in years:
        print(
            f"{row['year']:>4} {float(row['total_profit_base']):>16,.0f} "
            f"{float(row['total_profit_scenario']):>16,.0f} {float(row['total_profit_diff']):>+16,.0f}"
        )
    if firms:
        loser, winner = firms[0], firms[-1]
        print(f"Biggest loser: {loser['firm']} ({float(loser['cumulative_profit_diff']):+,.0f})")
        print(f"Biggest winner: {winner['firm']} ({float(winner['cumulative_profit_diff']):+,.0f})")


def main(argv: list[str] | None = None) -> RunResult:
    parser = argparse.ArgumentParser(description="Fork a saved run into a what-if scenario")
    parser.add_argument("--from", dest="checkpoint", required=True, help="self-generated checkpoint")
    parser.add_argument("--scenario", required=True, help="name from config/scenarios.yaml")
    parser.add_argument("--out", required=True)
    parser.add_argument("--baseline", help="directory with the baseline run's CSVs")
    args = parser.parse_args(argv)
    scenario = get_scenario(args.scenario)
    print(f"Scenario {scenario.name}: {scenario.description}")
    result = run_fork(args.checkpoint, scenario)
    write_outputs(result, args.out)
    print_summary(result)
    if args.baseline:
        _print_comparison(*write_comparison(args.baseline, args.out, args.out))
    return result


if __name__ == "__main__":
    main()
