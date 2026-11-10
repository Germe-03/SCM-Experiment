"""Phase 52: classify firms into the existing strategies from their observed behaviour.

Firms do not choose a strategy. They act freely (price, wage, R&D, stock, risk, overtime) and are
relabelled every year with the nearest archetype prototype, measured on standardised features.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from market_sim.policies import FirmPolicy

if TYPE_CHECKING:
    from market_sim.config import MarketConfig
    from market_sim.models import Firm
    from market_sim.strategy import AnnualStrategy

FEATURES = ("price", "wage", "rnd", "quality", "stock", "risk", "overtime")


def prototype(stage: str, archetype: str) -> list[float]:
    """Return the feature vector an archetype stands for at a given stage."""
    price, wage, rnd, quality, _priority, stock, risk, _hires, overtime = FirmPolicy._PRESETS[archetype]
    return [FirmPolicy.price_position(stage, archetype), wage, rnd, quality, float(stock), risk, overtime]


def observe(firm: Firm, strategy: AnnualStrategy, config: MarketConfig) -> list[float]:
    """Return the standardised-input feature vector of what a firm actually does this year."""
    band = config.stage_prices[firm.stage]
    low = max(band.min, 0.8 * band.base)
    high = min(band.max, 1.3 * band.base)
    span = max(1e-9, high - low)
    wage_base = float(firm.initial_wage_level or 0.0)
    rnd_base = float(firm.initial_r_and_d_budget or 0.0)
    return [
        (strategy.base_price - low) / span,
        strategy.wage_level / wage_base if wage_base > 0 else 1.0,
        strategy.r_and_d_budget / rnd_base if rnd_base > 0 else 1.0,
        strategy.target_quality,
        float(strategy.target_safety_stock_days),
        strategy.risk_tolerance,
        strategy.overtime_level,
    ]


def _scales(stage: str) -> list[float]:
    vectors = [prototype(stage, a) for a in sorted(FirmPolicy._PRESETS)]
    scales = []
    for i in range(len(FEATURES)):
        values = [v[i] for v in vectors]
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))
        scales.append(sd if sd > 1e-9 else 1.0)
    return scales


def distances(stage: str, features: list[float]) -> dict[str, float]:
    """Return the standardised Euclidean distance to each archetype prototype."""
    scales = _scales(stage)
    out = {}
    for archetype in sorted(FirmPolicy._PRESETS):
        proto = prototype(stage, archetype)
        out[archetype] = math.sqrt(sum(((f - p) / s) ** 2 for f, p, s in zip(features, proto, scales)))
    return out


def classify(stage: str, features: list[float], current: str | None = None,
             hysteresis: float = 0.0) -> str:
    """Return the nearest archetype; keep `current` unless the winner is clearly closer."""
    dist = distances(stage, features)
    best = min(sorted(dist), key=lambda a: dist[a])
    if current in dist and best != current and dist[best] > dist[current] * (1 - hysteresis):
        return current
    return best
