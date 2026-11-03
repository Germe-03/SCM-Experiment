"""Command-line entry point and CSV output for the market simulation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from market_sim.checkpoint import load_checkpoint, year_end_saver
from market_sim.config import MarketConfig, load_market_config
from market_sim.kpi import AnnualReport, SystemKPIs
from market_sim.models import STAGES, SupplyNetwork, load_firms
from market_sim.policies import policies_for_network
from market_sim.runner import RunResult, SimulationRunner


EVENT_FIELDS = ["year", "day", "firm", "event", "details"]


def run_simulation(
    years: int | None = None,
    seed: int = 0,
    days_per_year: int | None = None,
    config: MarketConfig | None = None,
    network: SupplyNetwork | None = None,
    checkpoint_dir: str | Path | None = None,
) -> RunResult:
    """Load defaults and execute the complete rule-based market simulation."""

    runner, run_years = build_runner(years, seed, days_per_year, config, network)
    saver = year_end_saver(checkpoint_dir) if checkpoint_dir is not None else None
    return runner.continue_run(runner.start(), run_years, on_year_end=saver)


def build_runner(
    years: int | None = None,
    seed: int = 0,
    days_per_year: int | None = None,
    config: MarketConfig | None = None,
    network: SupplyNetwork | None = None,
) -> tuple[SimulationRunner, int]:
    """Create a runner with the default rule-based policies and its run length."""

    config = config or load_market_config()
    network = network or load_firms()
    run_years = config.simulation.years if years is None else years
    run_days = config.simulation.days_per_year if days_per_year is None else days_per_year
    if run_years < 0:
        raise ValueError("years must be non-negative")
    if run_days <= 0:
        raise ValueError("days_per_year must be positive")
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={
            "years": max(1, run_years), "days_per_year": run_days,
        })
    })
    firms = [firm for stage in network.stages for firm in stage.firms]
    runner = SimulationRunner(
        network, config, policies_for_network(firms), seed=seed,
    )
    return runner, run_years


def resume_simulation(checkpoint: str | Path, checkpoint_dir: str | Path | None = None) -> RunResult:
    """Continue a saved run up to its configured end year."""

    runner, state = load_checkpoint(checkpoint)
    saver = year_end_saver(checkpoint_dir) if checkpoint_dir is not None else None
    return runner.continue_run(state, runner.config.simulation.years, on_year_end=saver)


def _ranking_rows(result: RunResult) -> list[dict[str, object]]:
    cumulative = {
        firm.id: sum(year[firm.id].profit for year in result.annual_reports)
        for stage in result.network.stages for firm in stage.firms
    }
    final_reports = result.annual_reports[-1] if result.annual_reports else {}
    rows = []
    for stage in STAGES:
        for firm in result.network.firms_in(stage):
            report = final_reports.get(firm.id)
            rows.append({
                "firm": firm.id,
                "stage": firm.stage,
                "archetype": firm.archetype,
                "cumulative_profit": cumulative[firm.id],
                "final_cash": result.final_result.firm_results[firm.id].cash,
                "exit_year": result.exits.get(firm.id, ""),
                "final_reputation": report.reputation if report else firm.reputation,
                "final_market_share": report.market_share if report else "",
            })
    return sorted(rows, key=lambda row: (-float(row["cumulative_profit"]), str(row["firm"])))


def write_outputs(result: RunResult, out_dir: str | Path) -> list[Path]:
    """Write annual reports, system KPIs, and the final firm ranking as CSV."""

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    annual_path = directory / "annual_reports.csv"
    system_path = directory / "system_kpis.csv"
    ranking_path = directory / "firm_ranking.csv"
    events_path = directory / "events.csv"

    annual_fields = list(AnnualReport.model_fields)
    with annual_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=annual_fields)
        writer.writeheader()
        for reports in result.annual_reports:
            for firm_id in sorted(reports):
                row = reports[firm_id].model_dump()
                row["supplier_reliability"] = "|".join(
                    f"{supplier}:{value:.6g}"
                    for supplier, value in sorted(row["supplier_reliability"].items())
                )
                row["main_problems"] = "; ".join(row["main_problems"])
                writer.writerow(row)

    system_fields = list(SystemKPIs.model_fields)
    with system_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=system_fields)
        writer.writeheader()
        writer.writerows(kpi.model_dump() for kpi in result.system_kpis)

    ranking_rows = _ranking_rows(result)
    with ranking_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(ranking_rows[0]) if ranking_rows else [
            "firm", "stage", "archetype", "cumulative_profit", "final_cash", "exit_year",
            "final_reputation", "final_market_share",
        ])
        writer.writeheader()
        writer.writerows(ranking_rows)
    with events_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(result.events, key=lambda event: (event["year"], event["day"])))
    paths = [annual_path, system_path, ranking_path, events_path]
    # Phase 2: brand and consumer-class reports exist only in the classes model.
    for name, rows in (("brand_report.csv", result.brand_reports), ("class_report.csv", result.class_reports),
                       ("rnd_projects.csv", result.rnd_reports)):
        if rows:
            path = directory / name
            with path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            paths.append(path)
    path = directory / "offence_ledger.csv"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["firm", "offence", "year", "gain", "fine", "damage", "net", "paid_off"])
        writer.writeheader()
        writer.writerows(result.offence_ledger)
    paths.append(path)
    return paths


def print_summary(result: RunResult) -> None:
    """Print the profit ranking and annual system stability indicators."""

    rows = _ranking_rows(result)
    print("\nFirm ranking")
    print(f"{'firm':<18} {'stage':<12} {'archetype':<11} {'cum. profit':>14} {'final cash':>14} {'market share':>12}")
    for row in rows:
        share = row["final_market_share"]
        share_text = f"{float(share):.2%}" if share != "" else "-"
        print(
            f"{str(row['firm']):<18} {str(row['stage']):<12} {str(row['archetype']):<11} "
            f"{float(row['cumulative_profit']):>14,.2f} {float(row['final_cash']):>14,.2f} {share_text:>12}"
        )
    if rows:
        print(f"Market leader: {rows[0]['firm']} (cumulative profit {float(rows[0]['cumulative_profit']):,.2f})")
    exited = [
        f"{row['firm']} (after year {row['exit_year']})"
        for row in rows if row["exit_year"] != ""
    ]
    if exited:
        print("Exited (bankrupt): " + ", ".join(exited))
    insolvent = [
        str(row["firm"]) for row in rows
        if row["exit_year"] == "" and float(row["final_cash"]) < 0
    ]
    if insolvent:
        print("WARNING: negative final cash but still active: " + ", ".join(insolvent))

    print("\nYear-by-year system KPIs")
    print(f"{'year':>4} {'total profit':>14} {'bullwhip':>12} {'concentration':>14} {'lost sales':>12}")
    for kpi in result.system_kpis:
        print(
            f"{kpi.year:>4} {kpi.total_profit:>14,.2f} {kpi.bullwhip_ratio:>12.4f} "
            f"{kpi.market_concentration:>14.4f} {kpi.total_lost_sales:>12}"
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the multi-year market simulation")
    parser.add_argument("--years", type=int, default=None, help="simulation years (default: config)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--days-per-year", type=int, default=None)
    parser.add_argument("--out", default="runs")
    parser.add_argument(
        "--checkpoints", action="store_true",
        help="save <out>/checkpoints/year_XX.pkl after every simulated year",
    )
    parser.add_argument(
        "--resume", metavar="CHECKPOINT",
        help="continue a self-generated checkpoint to the configured end year",
    )
    args = parser.parse_args(argv)
    checkpoint_dir = Path(args.out) / "checkpoints" if args.checkpoints else None
    if args.resume:
        result = resume_simulation(args.resume, checkpoint_dir)
    else:
        result = run_simulation(
            args.years, args.seed, args.days_per_year, checkpoint_dir=checkpoint_dir,
        )
    write_outputs(result, args.out)
    print_summary(result)


if __name__ == "__main__":
    main()
