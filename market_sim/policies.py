"""Deterministic, rule-based S8 archetype policies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_sim.config import MarketConfig
from market_sim.models import Firm
from market_sim.strategy import AnnualStrategy, DailyDecision, FirmObservation

if TYPE_CHECKING:
    from market_sim.runner import YearSummary


class FirmPolicy:
    """Rule-based policy interface and default archetype implementation."""

    _PRESETS = {
        # S8 decisions: (price position, wage, R&D, quality, priority, stock, risk, hires, OT)
        "low_cost": (0.18, 0.90, 0.65, 0.62, "price", 4, 0.30, 0, 0.10),
        "standard": (0.50, 1.00, 1.00, 0.72, "reliability", 7, 0.50, 0, 0.20),
        "premium": (0.82, 1.12, 1.50, 0.90, "quality", 8, 0.60, 1, 0.25),
        "reliable": (0.58, 1.05, 1.10, 0.78, "reliability", 14, 0.35, 0, 0.15),
        "growth": (0.35, 1.03, 1.20, 0.76, "capacity", 9, 0.75, 3, 0.45),
    }

    def decide_annual(
        self, firm: Firm, last_summary: "YearSummary | None", config: MarketConfig
    ) -> AnnualStrategy:
        preset = self._PRESETS.get(firm.archetype, self._PRESETS["standard"])
        price_position, wage, rnd, quality, priority, stock, risk, hires, overtime = preset
        stage_band = config.stage_prices[firm.stage]
        span = stage_band.max - stage_band.min
        archetype_price = stage_band.min + span * price_position
        # P3 fix: retain a light own-price anchor inside the stage band.
        anchor = max(stage_band.min, min(stage_band.max, firm.sell_price))
        base = max(stage_band.min, min(stage_band.max, 0.25 * anchor + 0.75 * archetype_price))
        half_band = span * 0.10
        low = max(stage_band.min, base - half_band)
        high = min(stage_band.max, base + half_band)
        if last_summary is None:
            effective_hires = hires if firm.archetype == "growth" else 0
        elif last_summary.capacity_utilization > 0.85:
            effective_hires = hires
        elif last_summary.capacity_utilization < 0.40:
            effective_hires = -min(1, max(0, firm.employees - 5))
        else:
            effective_hires = 0
        return AnnualStrategy(
            positioning=firm.archetype,
            base_price=base, min_price=low, max_price=high,
            wage_level=max(0.0, float(firm.initial_wage_level) * wage),
            r_and_d_budget=max(0.0, float(firm.initial_r_and_d_budget) * rnd),
            target_quality=max(firm.quality_level, quality),
            supplier_priority=priority,
            target_safety_stock_days=stock,
            risk_tolerance=risk, hiring_plan=effective_hires, overtime_level=overtime,
        ).validate_for_config(config)

    def decide_daily(
        self, firm: Firm, obs: FirmObservation,
        strategy: AnnualStrategy, config: MarketConfig,
    ) -> DailyDecision:
        # S8 decision: base-stock ordering uses only locally observable state.
        demand = max(1.0, obs.recent_demand)
        target = round(strategy.target_safety_stock_days * demand)
        # P1 fix: on_order includes both in-transit and supplier-queued units.
        position = obs.inventory + obs.on_order - obs.backlog
        raw_order = max(0, target - position)
        # P1 fix: cap pathological spikes. Since orders are nonnegative and the
        # cap bounds every tick, their tick-to-tick increase is bounded by cap too.
        cap = round(config.policy.max_order_demand_multiple * demand)
        order_qty = min(raw_order, cap)

        price = strategy.base_price
        nudge = (strategy.max_price - strategy.min_price) * 0.25 * strategy.risk_tolerance
        if obs.backlog > 0 or obs.inventory < target * 0.5:
            price += nudge
        elif obs.inventory > target * 1.5:
            price -= nudge
        overtime = strategy.overtime_level
        if obs.backlog > demand:
            overtime = min(1.0, overtime + 0.2 * strategy.risk_tolerance)
        return DailyDecision(
            sell_price=strategy.clamp_price(price),
            order_qty=order_qty,
            overtime_level=overtime,
        )


def policies_for_network(firms: list[Firm]) -> dict[str, FirmPolicy]:
    """Build independent default policies for a collection of firms."""
    return {firm.id: FirmPolicy() for firm in firms}
