"""JSON-ready projection of simulation results for the HTML dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_sim.config import MarketConfig
from market_sim.kpi import PROJECT_DE
from market_sim.models import STAGES, SupplyNetwork
from market_sim.runner import RunResult
from market_sim.stock_market import EtfBook


def _weekly(values: list[float]) -> list[float]:
    """Weekly means keep 50-year runs small enough for one HTML file."""
    return [sum(values[i:i + 7]) / len(values[i:i + 7]) for i in range(0, len(values), 7)]


def _weekly_selection(rows: list[dict[str, Any]]) -> list[int]:
    """Indices of weekly and year-end closes."""
    return sorted(set(range(6, len(rows), 7)) | {
        i for i, row in enumerate(rows)
        if i == len(rows) - 1 or row["year"] != rows[i + 1]["year"]
    })


def _etf_weekly(stock_rows: list[dict[str, Any]], etf_rows: list[dict[str, Any]],
                definitions: list[dict[str, Any]], weighting: str,
                stock_cfg=None) -> dict[str, Any] | None:
    """Phase 23: ETF levels on the same weekly points as the share prices."""
    if not definitions or len(etf_rows) != len(stock_rows):
        return None
    selected = _weekly_selection(stock_rows)
    result = {
        "weighting": weighting,
        "definitions": definitions,
        "levels": {d["id"]: [round(etf_rows[i][d["id"]], 4) if etf_rows[i].get(d["id"]) is not None else None
                             for i in selected] for d in definitions},
    }
    if stock_cfg is not None:
        book = EtfBook(stock_cfg)
        book.definitions = {d["id"]: d for d in definitions}
        result["config"] = {
            "min_price": stock_cfg.etf_min_price,
            "min_members": stock_cfg.etf_min_members,
            "max_weight": stock_cfg.etf_max_weight,
        }
        result["members"] = {
            d["id"]: [len(book.eligible_members(d["id"], stock_rows[i])) for i in selected]
            for d in definitions
        }
        result["weights"] = {
            d["id"]: [
                [[fid, round(weight, 6)] for fid, weight in
                 sorted(book.weights(d["id"], stock_rows[i]).items(),
                        key=lambda item: item[1], reverse=True)]
                for i in selected
            ]
            for d in definitions
        }
    return result


def _stock_weekly(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep weekly and year-end closes, with gaps around listings."""
    closes = [rows[i] for i in _weekly_selection(rows)]
    ids = sorted({key for row in rows for key in row} - {"global_day", "year", "day", "index"})
    rounded = lambda value: round(value, 2) if value is not None else None
    return {
        "days": [row["global_day"] for row in closes],
        "years": [row["year"] for row in closes],
        "index": [rounded(row.get("index")) for row in closes],
        # Small nominal prices must retain precision for rebased comparisons.
        "prices": {fid: [round(row[fid], 6) if row.get(fid) is not None else None
                         for row in closes] for fid in ids},
    }


def _rnd_trees(config: MarketConfig) -> dict[str, list[dict[str, Any]]]:
    """Phase 27: research tree definitions for the tree graphics (empty when trees are off)."""
    if not config.research.trees_enabled:
        return {}
    return {
        tree: [{"name": s.name, "label": PROJECT_DE.get(s.name, s.name), "requires": list(s.requires),
                "complexity": s.complexity, "patentable": s.patentable, "branch": s.branch,
                "categories": list(s.categories)} for s in stages]
        for tree, stages in config.research.trees.items()
    }


def _population_matrix(class_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Phase 37: persons per year, age group, income level and drinking habit."""
    return [
        {"year": r["year"], "income_level": r["income_level"], "age_group": r["age_group"],
         "drinking_habit": r["drinking_habit"], "persons": r["persons"]}
        for r in class_reports
    ]


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
         "category": f.category, "importer": f.importer, "region": f.region, "channel": f.channel,
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
            report.setdefault("paid_items", {})
            report.setdefault("sold_items", {})
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
    bank_names = {row.bank_id: row.name for row in result.bank_history}
    bank_events = []
    for event in result.events:
        for bank_id, name in bank_names.items():
            direct = event["event"] in {"bank_failed", "bank_entry", "bank_payout"} and event["firm"] == bank_id
            indirect = event["event"] in {"credit_rejected", "account_opened", "bank_switched"} and name in event.get("details", "")
            if direct or indirect:
                bank_events.append({**event, "bank_id": bank_id})
    return {
        "meta": {
            "years": result.years,
            "days_per_year": config.simulation.days_per_year,
            "days_total": result.days_total,
            "shares_per_firm": config.stock_market.shares_per_firm,
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "firms": identities,
        },
        "firms": firm_data,
        "system": [item.model_dump(mode="json") for item in result.system_kpis],
        "banks": [item.model_dump(mode="json") for item in result.bank_history],
        "bank_events": bank_events,
        "stocks": _stock_weekly(result.stock_daily),
        "etfs": _etf_weekly(result.stock_daily, result.etf_daily, result.etf_definitions,
                            config.stock_market.etf_weighting, config.stock_market),
        "events": list(result.events),
        "ranking": ranking,
        "brands": list(result.brand_reports),
        "classes": list(result.class_reports),
        "population_matrix": _population_matrix(result.class_reports),
        "rnd": list(result.rnd_reports),
        "patents": list(result.patents),
        "rnd_trees": _rnd_trees(config),
        "carriers": list(result.carriers),
        "trucks": dict(result.trucks),
        "offence_ledger": list(result.offence_ledger),
        "holdings": list(result.holdings),
        "holding_groups": list(result.holding_groups),
        "project_labels": dict(PROJECT_DE),
        "holding_log": list(result.holding_log),
        "mergers": list(result.merger_log),
        "laws": list(result.laws),
        "commodities": list(result.commodities),
        "commodity_by_category": dict(config.commodities.components_by_category),
        # Yearly decisions only; the monthly order and price averages stay in decisions.csv.
        "decisions": [d for d in result.decisions if d.get("month") is None],
        "exit_analysis": result.exit_analysis,
        "regions": [r.model_dump() for r in config.geography.regions],
        "region_reports": result.region_reports,
        "firm_locations": result.firm_locations,
        "personas": result.personas,

    }
