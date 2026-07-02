"""Deterministic supplier scoring for the multi-firm market."""

from __future__ import annotations

from math import floor

from market_sim.config import SupplierScoreWeights
from market_sim.models import Firm


_FACTORS = (
    "price", "reliability", "quality", "reputation", "lead_time", "capacity",
)


def _minmax(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if high == low:
        return [1.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def _supplier_scores(
    downstream: Firm,
    candidates: list[Firm],
    weights: SupplierScoreWeights,
    lead_times: dict[str, int] | None,
    priority_boost: float = 2.0,
) -> tuple[list[Firm], dict[str, float]]:
    """Return S4-compatible normalized scores in deterministic id order."""

    ordered = sorted(candidates, key=lambda firm: firm.id)
    lead_times = lead_times or {firm.id: 0 for firm in ordered}
    price = [1.0 - value for value in _minmax([f.sell_price for f in ordered])]
    capacity = _minmax([float(f.capacity) for f in ordered])
    lead_time = [
        1.0 - value
        for value in _minmax([float(lead_times[f.id]) for f in ordered])
    ]
    components = {
        firm.id: {
            "price": price[index],
            "reliability": firm.reliability,
            "quality": firm.quality_level,
            "reputation": firm.reputation,
            "lead_time": lead_time[index],
            "capacity": capacity[index],
        }
        for index, firm in enumerate(ordered)
    }
    adjusted = {factor: float(getattr(weights, factor)) for factor in _FACTORS}
    if downstream.supplier_priority in adjusted:
        adjusted[downstream.supplier_priority] *= priority_boost
    total_weight = sum(adjusted.values())
    adjusted = {key: value / total_weight for key, value in adjusted.items()}
    return ordered, {
        firm.id: sum(adjusted[key] * components[firm.id][key] for key in _FACTORS)
        for firm in ordered
    }


def select_supplier(
    downstream: Firm,
    candidates: list[Firm],
    weights: SupplierScoreWeights,
    lead_times: dict[str, int] | None = None,
    active_firm_ids: set[str] | None = None,
) -> Firm | None:
    """Select the highest-scoring allowed supplier, breaking ties by id."""

    if active_firm_ids is not None:
        candidates = [firm for firm in candidates if firm.id in active_firm_ids]
    # P4b fix: a firm with no active supplier cannot source this tick.
    if not candidates:
        return None
    ordered, scores = _supplier_scores(downstream, candidates, weights, lead_times)
    return min(ordered, key=lambda firm: (-scores[firm.id], firm.id))


def split_order(
    downstream: Firm,
    candidates: list[Firm],
    order_qty: int,
    weights: SupplierScoreWeights,
    lead_times: dict[str, int] | None = None,
    concentration: float = 4.0,
    active_firm_ids: set[str] | None = None,
    priority_boost: float = 2.0,
) -> dict[str, int]:
    """P2 fix: split an order by supplier score using largest remainders."""

    if active_firm_ids is not None:
        candidates = [firm for firm in candidates if firm.id in active_firm_ids]
    # P4b fix: an empty active candidate set is a valid unsourced order.
    if not candidates:
        return {}
    ordered, scores = _supplier_scores(
        downstream, candidates, weights, lead_times, priority_boost
    )
    quantity = max(0, int(order_qty))
    weighted = {firm.id: scores[firm.id] ** concentration for firm in ordered}
    total_weight = sum(weighted.values())
    if total_weight == 0:
        weighted = {firm.id: 1.0 for firm in ordered}
        total_weight = float(len(ordered))
    quotas = {firm.id: quantity * weighted[firm.id] / total_weight for firm in ordered}
    allocation = {firm.id: floor(quotas[firm.id]) for firm in ordered}
    remaining = quantity - sum(allocation.values())
    ranking = sorted(
        allocation,
        key=lambda firm_id: (-(quotas[firm_id] - floor(quotas[firm_id])), firm_id),
    )
    for firm_id in ranking[:remaining]:
        allocation[firm_id] += 1
    return allocation
