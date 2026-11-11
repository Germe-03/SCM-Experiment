from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from market_sim.config import MarketConfig
from market_sim.models import Firm
from market_sim.policies import FirmPolicy
from market_sim.strategy import AnnualStrategy, DailyDecision, FirmObservation

if TYPE_CHECKING:
    from market_sim.runner import YearSummary


@dataclass
class PlayerSettings:
    """Settings for a player-controlled firm."""

    base_price: float
    target_safety_stock_days: int = 7
    order_qty: int | None = None
    overtime_level: float = 0.2
    wage_level: float = 1.0
    r_and_d_budget: float = 0.0
    target_quality: float = 0.72
    hiring_plan: int = 0
    supplier_priority: str = "reliability"
    positioning: str = "standard"
    risk_tolerance: float = 0.5

    @classmethod
    def from_strategy(cls, strategy: AnnualStrategy) -> PlayerSettings:
        """Create settings from an annual strategy."""
        return cls(
            base_price=strategy.base_price,
            target_safety_stock_days=strategy.target_safety_stock_days,
            order_qty=None,
            overtime_level=strategy.overtime_level,
            wage_level=strategy.wage_level,
            r_and_d_budget=strategy.r_and_d_budget,
            target_quality=strategy.target_quality,
            hiring_plan=strategy.hiring_plan,
            supplier_priority=strategy.supplier_priority,
            positioning=strategy.positioning,
            risk_tolerance=strategy.risk_tolerance,
        )


class PlayerPolicy(FirmPolicy):
    """Policy for a player-controlled firm."""

    def __init__(self, settings: PlayerSettings):
        self.settings = settings

    def decide_annual(
        self,
        firm: Firm,
        last_summary: YearSummary | None,
        config: MarketConfig,
        rival_price: float | None = None,
    ) -> AnnualStrategy:
        """Build the annual strategy from player settings."""
        band = config.stage_prices[firm.stage]
        lo = max(band.min, config.price.min)
        hi = min(band.max, config.price.max)
        base = min(max(self.settings.base_price, lo), hi)
        return AnnualStrategy(
            positioning=self.settings.positioning,
            base_price=base,
            min_price=lo,
            max_price=hi,
            wage_level=self.settings.wage_level,
            r_and_d_budget=self.settings.r_and_d_budget,
            target_quality=self.settings.target_quality,
            supplier_priority=self.settings.supplier_priority,
            target_safety_stock_days=self.settings.target_safety_stock_days,
            risk_tolerance=self.settings.risk_tolerance,
            hiring_plan=self.settings.hiring_plan,
            overtime_level=self.settings.overtime_level,
        ).validate_for_config(config)

    def decide_daily(
        self,
        firm: Firm,
        obs: FirmObservation,
        strategy: AnnualStrategy,
        config: MarketConfig,
    ) -> DailyDecision:
        """Build a daily decision from player settings and observations."""
        sell_price = strategy.clamp_price(self.settings.base_price)
        if self.settings.order_qty is not None:
            order_qty = max(0, int(self.settings.order_qty))
        else:
            demand = max(1.0, obs.recent_demand)
            target = round(self.settings.target_safety_stock_days * demand)
            position = obs.inventory + obs.on_order - obs.backlog
            raw = max(0, target - position)
            cap = round(config.policy.max_order_demand_multiple * demand)
            order_qty = min(raw, cap)
        overtime_level = min(1.0, max(0.0, self.settings.overtime_level))
        return DailyDecision(
            sell_price=sell_price,
            order_qty=order_qty,
            overtime_level=overtime_level,
        )
