"""JSON-ready projection of simulation results for the HTML dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_sim.config import MarketConfig
from market_sim.models import STAGES, SupplyNetwork
from market_sim.runner import RunResult


def _weekly(values: list[float]) -> list[float]:
    """Weekly means keep 50-year runs small enough for one HTML file."""
    return [sum(values[i:i + 7]) / len(values[i:i + 7]) for i in range(0, len(values), 7)]


def build_dashboard_data(
    result: RunResult, network: SupplyNetwork, config: MarketConfig, seed: int,
) -> dict[str, Any]:
    """Build a fully JSON-serializable, actor-oriented dashboard payload."""

    firms = [
        firm for stage in STAGES
        for firm in sorted(network.firms_in(stage), key=lambda item: item.id)
    ]
    identities = [
        {"id": f.id, "name": f.name, "stage": f.stage, "archetype": f.archetype,
         "category": f.category, "importer": f.importer, "region": f.region,
         "entry_year": min((int(e["year"]) for e in result.events
                            if e["firm"] == f.id and e["event"] in ("market_entry", "spin_off")), default=1),
         "exit_year": result.exits.get(f.id)}
        for f in firms
    ]
    firm_data: dict[str, Any] = {}
    for firm in firms:
        yearly = []
        for index in range(result.years):
            report = result.annual_reports[index][firm.id].model_dump(mode="json")
            report.update(result.financial_breakdown[firm.id][index])
            yearly.append(report)
        firm_data[firm.id] = {
            **next(item for item in identities if item["id"] == firm.id),
            "yearly": yearly,
            "weekly": {key: _weekly(result.daily_series[firm.id][key]) for key in ("inventory", "backlog", "cash")},
            "events": [event for event in result.events if event["firm"] == firm.id],
        }

    final_reports = result.annual_reports[-1] if result.annual_reports else {}
    ranking = []
    for firm in firms:
        final = final_reports.get(firm.id)
        ranking.append({
            "firm_id": firm.id, "name": firm.name, "stage": firm.stage,
            "archetype": firm.archetype,
            "cumulative_profit": sum(
                item["profit"] for item in result.financial_breakdown[firm.id]
            ),
            "final_cash": result.final_result.firm_results[firm.id].cash,
            "final_market_share": (
                final.market_share if final is not None else None
            ),
        })
    ranking.sort(key=lambda item: (-item["cumulative_profit"], item["firm_id"]))
    return {
        "meta": {
            "years": result.years,
            "days_per_year": config.simulation.days_per_year,
            "days_total": result.days_total,
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "firms": identities,
        },
        "firms": firm_data,
        "system": [item.model_dump(mode="json") for item in result.system_kpis],
        "events": list(result.events),
        "ranking": ranking,
        "brands": list(result.brand_reports),
        "classes": list(result.class_reports),
        "rnd": list(result.rnd_reports),
        "offence_ledger": list(result.offence_ledger),
    }
