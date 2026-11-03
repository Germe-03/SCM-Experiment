"""Deterministic archetype policies with adaptive annual strategy."""

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
        # Discount firms operate near the floor; a narrow band prevents
        # scarcity pricing from eroding their positioning.
        "low_cost": (0.14, 0.90, 0.65, 0.62, "price", 6, 0.10, 0, 0.10),
        "standard": (0.50, 1.00, 1.00, 0.72, "reliability", 7, 0.50, 0, 0.20),
        "premium": (0.85, 1.12, 1.50, 0.90, "quality", 8, 0.60, 1, 0.25),
        "reliable": (0.58, 1.05, 1.10, 0.78, "reliability", 14, 0.35, 0, 0.15),
        "growth": (0.35, 1.03, 1.20, 0.76, "capacity", 9, 0.75, 3, 0.45),
    }

    def decide_annual(
        self, firm: Firm, last_summary: "YearSummary | None", config: MarketConfig,
        rival_price: float | None = None,
    ) -> AnnualStrategy:
        preset = self._PRESETS.get(firm.archetype, self._PRESETS["standard"])
        price_position, wage, rnd, quality, priority, stock, risk, hires, overtime = preset
        # The network has no low-cost factory. Its growth factory supplies the
        # discount chain and therefore needs a source-stage price position.
        if firm.stage == "factory" and firm.archetype == "growth":
            price_position = 0.2
        elif firm.archetype == "low_cost":
            # Discount firms sit about 12 % below the stage base price.
            price_position = 0.2
        elif firm.stage == "retailer":
            # Retail positions are calibrated to comparable ten-year returns:
            # premium earns margin without dominating, while the middle
            # strategies retain modest positive growth.
            price_position = {
                "standard": 0.457,
                "reliable": 0.50,
                "growth": 0.303,
                "premium": 0.58,
            }.get(firm.archetype, price_position)
        stage_band = config.stage_prices[firm.stage]
        # Firms position themselves around the stage base price, not across
        # the full (wide) safety band.
        band_low = max(stage_band.min, 0.8 * stage_band.base)
        band_high = min(stage_band.max, 1.3 * stage_band.base)
        span = band_high - band_low
        archetype_price = band_low + span * price_position
        # P3 fix: retain a light own-price anchor inside the stage band.
        anchor = max(band_low, min(band_high, firm.sell_price))
        base = max(band_low, min(band_high, 0.25 * anchor + 0.75 * archetype_price))
        positioning = firm.archetype
        rnd_multiplier = rnd
        stock_days = stock
        adaptive = config.adaptive_strategy

        if last_summary is not None:
            # Attribute-aware direction: quality/reputation must support premium;
            # structurally weaker quality is better served by a discount position.
            quality_signal = 0.7 * last_summary.quality + 0.3 * firm.reputation
            premium_capable = quality_signal >= 0.78
            discount_capable = quality_signal <= 0.69
            profitable = last_summary.profit > 0
            holding_share = last_summary.market_share_change >= -0.002
            weak_service = (
                last_summary.avg_backlog > 1.0
                or last_summary.service_level < 0.96
                or last_summary.lost_sales > 0
            )

            current = last_summary.avg_sell_price
            if not band_low <= current <= band_high:
                current = base
            step = span * adaptive.price_step_fraction
            cut_step = span * (adaptive.max_price_step_fraction or adaptive.price_step_fraction)
            target = archetype_price

            if premium_capable:
                positioning = "premium"
                target = band_low + min(0.64, price_position + 0.04) * span
                rnd_multiplier = rnd + adaptive.rnd_step_multiplier
                if profitable and holding_share:
                    target += 0.5 * step
            elif discount_capable:
                positioning = "low_cost"
                target = archetype_price
                rnd_multiplier = max(adaptive.rnd_min_multiplier, rnd - adaptive.rnd_step_multiplier)
                if not profitable:
                    # Preserve the discount position but repair an unsustainable
                    # unit margin instead of blindly cutting price again.
                    target = min(band_low + 0.22 * span, current + step)
            elif not profitable or not holding_share:
                # A weak middle firm differentiates toward the closest credible
                # edge instead of making a large, unsupported positioning jump.
                if quality_signal >= 0.735:
                    positioning, target = "premium", band_low + 0.60 * span
                    rnd_multiplier = rnd + adaptive.rnd_step_multiplier
                else:
                    positioning, target = "low_cost", band_low + 0.20 * span
                    rnd_multiplier = max(adaptive.rnd_min_multiplier, rnd - adaptive.rnd_step_multiplier)

            if adaptive.undercut_fraction:
                lost_share = last_summary.market_share_change < -adaptive.share_loss_trigger
                gained_share = last_summary.market_share_change > adaptive.share_loss_trigger
                anchor_price = rival_price if rival_price is not None else current
                if lost_share and profitable:
                    # Fight back: go slightly below the rivals' average price.
                    target = min(target, min(current, anchor_price) * (1 - adaptive.undercut_fraction))
                elif gained_share and profitable:
                    target = max(target, current * (1 + 0.5 * adaptive.undercut_fraction))
                if adaptive.competitive_pull and rival_price is not None:
                    target += adaptive.competitive_pull * (rival_price - target)

            base = current + max(-cut_step, min(step, target - current))
            base = max(band_low, min(band_high, base))
            if weak_service:
                stock_days += 1
            elif last_summary.capacity_utilization < 0.40 and last_summary.avg_inventory > 0:
                stock_days -= 1

        rnd_multiplier = max(
            adaptive.rnd_min_multiplier,
            min(adaptive.rnd_max_multiplier, rnd_multiplier),
        )
        stock_days = max(
            adaptive.safety_stock_min_days,
            min(adaptive.safety_stock_max_days, stock_days),
        )
        half_band = span * (0.02 if positioning == "low_cost" else 0.10)
        low = max(band_low, base - half_band)
        high = min(band_high, base + half_band)
        if last_summary is None:
            effective_hires = hires if firm.archetype == "growth" else 0
        elif last_summary.capacity_utilization > 0.85:
            effective_hires = min(adaptive.max_hires_per_year, max(1, hires))
        elif last_summary.capacity_utilization < 0.40:
            effective_hires = -min(1, max(0, firm.employees - 5))
        else:
            effective_hires = 0
        return AnnualStrategy(
            positioning=positioning,
            base_price=base, min_price=low, max_price=high,
            wage_level=max(0.0, float(firm.initial_wage_level) * wage),
            r_and_d_budget=max(0.0, float(firm.initial_r_and_d_budget) * rnd_multiplier),
            target_quality=max(firm.quality_level, quality),
            supplier_priority=priority,
            target_safety_stock_days=stock_days,
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
