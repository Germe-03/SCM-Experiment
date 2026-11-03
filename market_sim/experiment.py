"""Experiment runner: the full simulation over several seeds, summarised per metric.

Example::

    python -m market_sim.experiment --seeds 0-9 --out runs/experiment

Every seed runs the whole market on its own process; nothing is shared. Metrics
are taken over the years after ``--skip-years`` (the start-up phase).
"""

from __future__ import annotations

import argparse
import csv
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter

from market_sim.run import build_runner, write_outputs
from market_sim.runner import RunResult

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
    "takeovers": ("takeovers", "sum"),
    "offences": ("offences", "sum"),
    "poisonings": ("poisonings", "sum"),
    "rnd_successes": ("rnd_successes", "sum"),
    **{f"debt_{stage}": (f"debt_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"active_firms_{stage}": (f"active_firms_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"margin_{stage}": (f"margin_{stage}", "mean") for stage in STAGE_NAMES},
    **{f"utilization_{stage}": (f"utilization_{stage}", "mean") for stage in STAGE_NAMES},
}
HEADLINE = {
    "total_profit": "profit", "service_level": "service level",
    "market_concentration": "HHI", "bankruptcies": "bankruptcies",
    "market_entries": "entries", "takeovers": "takeovers",
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


def run_seed(task: tuple[int, int, str, int | None, int | None]) -> dict[str, object]:
    """Run one seed of the full simulation and return its metrics."""
    seed, skip_years, out, run_years, days = task
    started = perf_counter()
    runner, years = build_runner(run_years, seed, days)
    result = runner.continue_run(runner.start(), years)
    write_outputs(result, Path(out) / f"seed_{seed:02d}")
    return {"seed": seed, "exits": len(result.exits), "runtime_seconds": perf_counter() - started,
            **run_metrics(result, skip_years)}


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Mean, standard deviation, minimum and maximum of every metric over the seeds."""
    summary = []
    for metric in (*METRICS, "exits"):
        values = [float(row[metric]) for row in rows]
        summary.append({
            "metric": metric, "n": len(values),
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


def print_summary(summary: list[dict[str, object]], seeds: list[int], skip_years: int) -> None:
    print(f"\nExperiment: {len(seeds)} seeds, values from year {skip_years + 1} on")
    lookup = {row["metric"]: row for row in summary}
    for metric, label in HEADLINE.items():
        row = lookup[metric]
        print(f"  {label:<14} {row['mean']:>14,.4g} ± {row['std']:<10,.3g} (min {row['min']:,.4g}, max {row['max']:,.4g})")


def run_experiment(
    seeds: list[int], out: str | Path, skip_years: int = 0, workers: int = 1,
    years: int | None = None, days_per_year: int | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    _, total_years = build_runner(years, seeds[0], days_per_year)
    if not 0 <= skip_years < total_years:
        raise ValueError(f"skip years must lie between 0 and {total_years - 1}")
    tasks = [(seed, skip_years, str(out), years, days_per_year) for seed in seeds]
    if workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
            rows = list(pool.map(run_seed, tasks))
    else:
        rows = [run_seed(task) for task in tasks]
    summary = summarize(rows)
    write_experiment(Path(out), rows, summary)
    return rows, summary


def main(argv: list[str] | None = None) -> list[dict[str, object]]:
    parser = argparse.ArgumentParser(description="Run the full simulation over several seeds")
    parser.add_argument("--seeds", default="0-4", help="e.g. 0-9 or 0,2,5")
    parser.add_argument("--skip-years", type=int, default=0, help="start-up years left out of the metrics")
    parser.add_argument("--years", type=int, default=None, help="simulation years (default: config)")
    parser.add_argument("--days-per-year", type=int, default=None)
    parser.add_argument("--out", default="runs/experiment")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                        help="parallel processes (one per seed)")
    args = parser.parse_args(argv)
    seeds = parse_seeds(args.seeds)
    _, summary = run_experiment(seeds, args.out, args.skip_years, args.workers, args.years, args.days_per_year)
    print_summary(summary, seeds, args.skip_years)
    print(f"\nWritten to {Path(args.out) / 'experiment_summary.csv'}")
    return summary


if __name__ == "__main__":
    main()
