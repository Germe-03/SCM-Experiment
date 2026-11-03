"""Experiment runner: several seeds times several scenarios, compared after the fork year.

Example::

    python -m market_sim.experiment --seeds 0-9 \
        --scenarios basis,nachfrage_einbruch,brauerei_engpass,preiserhoehung_brauerei \
        --fork-year 5 --out runs/experiment_a

Every seed first runs the baseline and saves its year-end checkpoint at the fork
year. Each scenario is then forked from a freshly loaded copy of that checkpoint,
so no scenario and no seed can influence another one. All metrics are taken over
the years after the fork year, where scenarios can differ.
"""

from __future__ import annotations

import argparse
import csv
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter

from market_sim.checkpoint import checkpoint_path, save_checkpoint
from market_sim.run import build_runner, write_outputs
from market_sim.runner import RunResult, SimulationRunner, RunState
from market_sim.scenario import get_scenario, run_fork

BASELINE = "basis"
STAGE_NAMES = ("retailer", "wholesaler", "distributor", "factory")
# metric -> how the yearly system KPI values are combined over the compared years
METRICS: dict[str, tuple[str, str]] = {
    "total_profit": ("total_profit", "sum"),
    "total_lost_sales": ("total_lost_sales", "sum"),
    "average_customer_price": ("average_customer_price", "mean"),
    "market_concentration": ("market_concentration", "mean"),
    "bullwhip_ratio": ("bullwhip_ratio", "mean"),
    "service_level": ("service_level", "mean"),
    "market_share_movement": ("market_share_movement", "mean"),
    "firms_with_loss": ("firms_with_loss", "mean"),
    "retailer_price_spread": ("retailer_price_spread", "mean"),
    "bankruptcies": ("bankruptcies", "sum"),
    "market_entries": ("market_entries", "sum"),
    "strategy_changes": ("strategy_changes", "sum"),
    **{f"interest_cost_{stage}": (f"interest_cost_{stage}", "sum") for stage in STAGE_NAMES},
    **{f"debt_{stage}": (f"debt_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"active_firms_{stage}": (f"active_firms_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"margin_{stage}": (f"margin_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"utilization_{stage}": (f"utilization_{stage}", "mean") for stage in STAGE_NAMES},
}
HEADLINE = {
    "total_profit": "profit", "total_lost_sales": "lost sales",
    "average_customer_price": "price", "market_concentration": "HHI",
    "service_level": "service level", "bankruptcies": "bankruptcies",
}


def parse_seeds(text: str) -> list[int]:
    """Parse ``0-9``, ``0,2,5`` or ``0-3,7`` into a sorted list of unique seeds."""
    seeds: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        first, dash, last = part.partition("-")
        low, high = int(first), int(last) if dash else int(first)
        if high < low:
            raise ValueError(f"empty seed range {part!r}")
        seeds.update(range(low, high + 1))
    if not seeds:
        raise ValueError("no seeds given")
    return sorted(seeds)


def run_metrics(result: RunResult, after_year: int) -> dict[str, float]:
    """Combine the system KPIs of the years after ``after_year`` into one value each."""
    kpis = result.system_kpis[after_year:]
    values: dict[str, float] = {}
    for name, (field, how) in METRICS.items():
        series = [float(getattr(item, field)) for item in kpis]
        values[name] = (sum(series) if how == "sum" else mean(series)) if series else 0.0
    return values


def run_seed(task: tuple[int, tuple[str, ...], int, str, int | None, int | None]) -> list[dict[str, object]]:
    """Run the baseline and all scenarios of one seed; return one row per scenario."""
    seed, scenarios, fork_year, out, run_years, days = task
    started = perf_counter()
    runner, years = build_runner(run_years, seed, days)
    path = checkpoint_path(Path(out) / "checkpoints" / f"seed_{seed:02d}", fork_year)

    def save_at_fork_year(sim: SimulationRunner, state: RunState) -> None:
        if state.year == fork_year:
            save_checkpoint(sim, state, path)

    baseline = runner.continue_run(runner.start(), years, on_year_end=save_at_fork_year)
    elapsed = perf_counter() - started
    rows = []
    for name in scenarios:
        result = baseline if name == BASELINE else run_fork(path, get_scenario(name))
        write_outputs(result, Path(out) / f"seed_{seed:02d}" / name)
        rows.append({
            "scenario": name, "seed": seed, "exits": len(result.exits),
            "runtime_seconds": elapsed,
            **run_metrics(result, fork_year),
        })
    return rows


def summarize(rows: list[dict[str, object]], scenarios: list[str]) -> list[dict[str, object]]:
    """Mean, standard deviation, minimum and maximum of every metric per scenario."""
    summary = []
    for name in scenarios:
        scoped = [row for row in rows if row["scenario"] == name]
        for metric in (*METRICS, "exits"):
            values = [float(row[metric]) for row in scoped]
            summary.append({
                "scenario": name, "metric": metric, "n": len(values),
                "mean": mean(values), "std": pstdev(values) if len(values) > 1 else 0.0,
                "min": min(values), "max": max(values),
            })
    return summary


def write_experiment(out: Path, rows: list[dict[str, object]], summary: list[dict[str, object]]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for file_name, data in (("experiment_runs.csv", rows), ("experiment_summary.csv", summary)):
        path = out / file_name
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
        paths.append(path)
    return paths


def print_summary(summary: list[dict[str, object]], scenarios: list[str], seeds: list[int], fork_year: int) -> None:
    print(f"\nExperiment: {len(seeds)} seeds, fork after year {fork_year} (values: years {fork_year + 1}+)")
    lookup = {(row["scenario"], row["metric"]): row for row in summary}
    print(f"{'scenario':<26}" + "".join(f"{label:>20}" for label in HEADLINE.values()))
    for name in scenarios:
        cells = []
        for metric in HEADLINE:
            row = lookup[(name, metric)]
            cells.append(f"{row['mean']:>11,.4g} ±{row['std']:<7,.3g}")
        print(f"{name:<26}" + "".join(f"{cell:>20}" for cell in cells))
    if BASELINE in scenarios:
        print(f"\nDifference to '{BASELINE}' (mean)")
        for name in scenarios:
            if name == BASELINE:
                continue
            diffs = ", ".join(
                f"{metric} {lookup[(name, metric)]['mean'] - lookup[(BASELINE, metric)]['mean']:+,.4g}"
                for metric in HEADLINE
            )
            print(f"  {name}: {diffs}")


def run_experiment(
    seeds: list[int], scenarios: list[str], fork_year: int, out: str | Path,
    workers: int = 1, years: int | None = None, days_per_year: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    for name in scenarios:
        if name != BASELINE:
            get_scenario(name)  # fail early on unknown names
    _, total_years = build_runner(years, seeds[0], days_per_year)
    if not 1 <= fork_year < total_years:
        raise ValueError(f"fork year must lie between 1 and {total_years - 1}")
    tasks = [(seed, tuple(scenarios), fork_year, str(out), years, days_per_year) for seed in seeds]
    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
            chunks = list(pool.map(run_seed, tasks))
    else:
        chunks = [run_seed(task) for task in tasks]
    rows = [row for chunk in chunks for row in chunk]
    summary = summarize(rows, scenarios)
    write_experiment(Path(out), rows, summary)
    return rows, summary


def main(argv: list[str] | None = None) -> list[dict[str, object]]:
    parser = argparse.ArgumentParser(description="Run several seeds and what-if scenarios")
    parser.add_argument("--seeds", default="0-4", help="e.g. 0-9 or 0,2,5")
    parser.add_argument("--scenarios", default=BASELINE, help="comma separated; 'basis' is the baseline")
    parser.add_argument("--fork-year", type=int, default=5)
    parser.add_argument("--years", type=int, default=None, help="simulation years (default: config)")
    parser.add_argument("--days-per-year", type=int, default=None)
    parser.add_argument("--out", default="runs/experiment")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                        help="parallel processes (one task per seed)")
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    scenarios = [name.strip() for name in args.scenarios.split(",") if name.strip()]
    if not scenarios:
        raise SystemExit("no scenarios given")
    _, summary = run_experiment(
        seeds, scenarios, args.fork_year, args.out, args.workers, args.years, args.days_per_year,
    )
    print_summary(summary, scenarios, seeds, args.fork_year)
    print(f"\nWritten to {Path(args.out) / 'experiment_summary.csv'}")
    return summary


if __name__ == "__main__":
    main()
