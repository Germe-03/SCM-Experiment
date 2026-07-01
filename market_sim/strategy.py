"""Validated contracts for the S8 annual and daily decision levels."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from market_sim.config import MarketConfig


class StrategyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnnualStrategy(StrategyModel):
    positioning: str
    base_price: float
    min_price: float
    max_price: float
    wage_level: float = Field(ge=0)
    r_and_d_budget: float = Field(ge=0)
    target_quality: float = Field(ge=0, le=1)
    supplier_priority: str
    target_safety_stock_days: int = Field(ge=0)
    risk_tolerance: float = Field(ge=0, le=1)
    hiring_plan: int
    overtime_level: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered_price_band(self) -> "AnnualStrategy":
        if not self.min_price <= self.base_price <= self.max_price:
            raise ValueError("strategy price must satisfy min_price <= base_price <= max_price")
        return self

    def validate_for_config(self, config: MarketConfig) -> "AnnualStrategy":
        """Validate the annual band against the configured market bounds."""
        if self.min_price < config.price.min or self.max_price > config.price.max:
            raise ValueError("strategy price band is outside configured market bounds")
        return self

    def clamp_price(self, price: float) -> float:
        return max(self.min_price, min(self.max_price, float(price)))


class DailyDecision(StrategyModel):
    sell_price: float
    order_qty: int = Field(ge=0)
    overtime_level: float = Field(ge=0, le=1)

    def clamped_to(self, strategy: AnnualStrategy) -> "DailyDecision":
        """Return an apply-safe decision constrained by the active strategy."""
        return self.model_copy(update={"sell_price": strategy.clamp_price(self.sell_price)})


class FirmObservation(StrategyModel):
    inventory: int = Field(ge=0)
    backlog: int = Field(ge=0)
    pipeline_units: int = Field(ge=0)
    recent_demand: float = Field(ge=0)
    recent_sales: float = Field(ge=0)
    cash: float
    day_of_year: int = Field(ge=0)
    quality_level: float = Field(ge=0, le=1)

