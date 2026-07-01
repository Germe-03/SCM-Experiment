"""Deterministic supplier scoring for the multi-firm market."""

from __future__ import annotations

from market_sim.config import SupplierScoreWeights
from market_sim.models import Firm


_FACTORS = ("price", "reliability", "quality", "lead_time", "capacity")


def _minmax(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if high == low:
        return [1.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def select_supplier(
    downstream: Firm,
    candidates: list[Firm],
    weights: SupplierScoreWeights,
    lead_times: dict[str, int] | None = None,
) -> Firm:
    """Select the highest-scoring allowed supplier, breaking ties by id."""

    if not candidates:
        raise ValueError(f"firm {downstream.id!r} has no supplier candidates")
    ordered = sorted(candidates, key=lambda firm: firm.id)
    lead_times = lead_times or {firm.id: 0 for firm in ordered}

    # S4 decision: normalize comparative factors within this firm's candidate set.
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
            "lead_time": lead_time[index],
            "capacity": capacity[index],
        }
        for index, firm in enumerate(ordered)
    }

    adjusted = {factor: float(getattr(weights, factor)) for factor in _FACTORS}
    # S4 decision: a recognized supplier priority doubles that factor's weight,
    # after which all weights are renormalized.
    if downstream.supplier_priority in adjusted:
        adjusted[downstream.supplier_priority] *= 2.0
    total_weight = sum(adjusted.values())
    adjusted = {key: value / total_weight for key, value in adjusted.items()}

    scores = {
        firm.id: sum(adjusted[key] * components[firm.id][key] for key in _FACTORS)
        for firm in ordered
    }
    return min(ordered, key=lambda firm: (-scores[firm.id], firm.id))
