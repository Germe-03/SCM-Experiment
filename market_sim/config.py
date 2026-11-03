"""Typed configuration for the Swiss beer market simulation."""

from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigModel(BaseModel):
    """Base class that rejects misspelled or unsupported configuration keys."""

    model_config = ConfigDict(extra="forbid")


class UnitScaleConfig(ConfigModel):
    real_units_per_sim_unit: int = Field(gt=0)


class AttractivenessWeights(ConfigModel):
    price: float
    quality: float
    reputation: float
    availability: float

    @model_validator(mode="after")
    def _weights_must_sum_to_one(self) -> Self:
        total = self.price + self.quality + self.reputation + self.availability
        if not isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(
                "demand attractiveness weights must sum to 1.0 "
                f"(got {total})"
            )
        return self


class DemandSegment(ConfigModel):
    """Demand-v2 customer segment with independently weighted priorities."""

    name: str = Field(min_length=1)
    share: float = Field(gt=0, le=1)
    weights: AttractivenessWeights


class DemandConfig(ConfigModel):
    annual_demand_units: int = Field(ge=0)
    daily_demand_units: int = Field(ge=0)
    # P4b fix: market size responds to price and the annual demand cycle.
    price_elasticity: float = Field(default=1.2, ge=0)
    reference_price: float = Field(default=4.99, gt=0)
    elasticity_min_mult: float = Field(default=0.3, gt=0)
    elasticity_max_mult: float = Field(default=2.0, gt=0)
    seasonal_amplitude: float = Field(default=0.25, ge=0, lt=1)
    seasonal_phase_days: float = 90.0
    segments: list[DemandSegment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _elasticity_bounds_must_be_ordered(self) -> Self:
        if self.elasticity_min_mult > self.elasticity_max_mult:
            raise ValueError("elasticity_min_mult must not exceed elasticity_max_mult")
        if self.segments:
            total = sum(segment.share for segment in self.segments)
            if not isclose(total, 1.0, abs_tol=1e-6):
                raise ValueError(f"demand segment shares must sum to 1.0 (got {total})")
            names = [segment.name for segment in self.segments]
            if len(names) != len(set(names)):
                raise ValueError("demand segment names must be unique")
        return self


class BankruptcyConfig(ConfigModel):
    """Market exit policy, relative to each firm's own starting capital."""

    enabled: bool = True
    # Exit when cash falls below -fraction * initial cash (None disables).
    cash_floor_fraction: float | None = Field(default=1.0, ge=0)
    # Exit after this many consecutive year-ends with negative cash (0 disables).
    negative_cash_years: int = Field(default=2, ge=0)
    # Exits never leave fewer active firms than this on a stage.
    min_firms_per_stage: int = Field(default=0, ge=0)
    # 0 means unlimited.
    max_exits_per_stage_per_year: int = Field(default=0, ge=0)
    # Optional absolute floor in CHF, kept for tests and special scenarios.
    cash_threshold: float | None = None
    min_years_before_exit: int = Field(default=1, ge=0)


class StartVariationConfig(ConfigModel):
    """Seeded relative spread (+/-) of the starting values of every firm."""

    cash_spread: float = Field(default=0.0, ge=0, lt=1)
    quality_spread: float = Field(default=0.0, ge=0, lt=1)
    reputation_spread: float = Field(default=0.0, ge=0, lt=1)


class MarketEventsConfig(ConfigModel):
    """Yearly random market events; probabilities are drawn once per year and seed."""

    heat_summer_probability: float = Field(default=0.0, ge=0, le=1)
    heat_summer_demand_factor: float = Field(default=1.15, gt=0)
    heat_summer_days: int = Field(default=60, gt=0)
    harvest_failure_probability: float = Field(default=0.0, ge=0, le=1)
    harvest_failure_cost_factor: float = Field(default=1.35, gt=0)
    recall_probability: float = Field(default=0.0, ge=0, le=1)
    recall_quality_hit: float = Field(default=0.10, ge=0, le=1)
    recall_reputation_hit: float = Field(default=0.15, ge=0, le=1)
    # One-off cost in real CHF.
    recall_cost: float = Field(default=0.0, ge=0)


class PriceConfig(ConfigModel):
    base: float
    min: float
    max: float

    @model_validator(mode="after")
    def _prices_must_be_ordered(self) -> Self:
        if not self.min <= self.base <= self.max:
            raise ValueError("price must satisfy min <= base <= max")
        return self


class StagePriceConfig(PriceConfig):
    """P3 fix: one validated selling-price band per supply-chain stage."""


class SimulationConfig(ConfigModel):
    years: int = Field(gt=0)
    days_per_year: int = Field(gt=0)


class LogisticsConfig(ConfigModel):
    default_lead_time_days: int = Field(ge=0)


class CostConfig(ConfigModel):
    holding_cost_per_unit: float = Field(ge=0)
    backlog_cost_per_unit: float = Field(ge=0)
    # Demand-v2 calibration knob: real CHF charged per sim-unit handled.
    handling_cost_per_unit: float = Field(default=0.0, ge=0)
    # One simulated employee/budget CHF stands for this many real ones, so
    # wages, hiring and R&D live on the same money scale as revenue.
    personnel_cost_scale: float = Field(default=1.0, gt=0)
    # Starting capital scale, so equity matches the revenue-scaled money.
    initial_cash_scale: float = Field(default=1.0, gt=0)


class FixedCostConfig(ConfigModel):
    """Rent, vehicles and machines in real CHF per day, by stage."""

    base_per_day: dict[str, float] = Field(default_factory=dict)
    per_capacity_unit_per_day: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _stages_known(self) -> Self:
        known = {"factory", "distributor", "wholesaler", "retailer"}
        for block in (self.base_per_day, self.per_capacity_unit_per_day):
            if set(block) - known:
                raise ValueError(f"fixed cost stages must be within {sorted(known)}")
            if any(value < 0 for value in block.values()):
                raise ValueError("fixed costs must not be negative")
        return self


class CommodityConfig(ConfigModel):
    """Raw materials per produced sim-unit (real CHF) with fluctuating price indices."""

    # Base cost per component, e.g. malt, hops, packaging, energy.
    components: dict[str, float] = Field(default_factory=dict)
    index_volatility: float = Field(default=0.0, ge=0)
    index_mean_reversion: float = Field(default=0.2, ge=0, le=1)
    index_update_days: int = Field(default=30, gt=0)

    @model_validator(mode="after")
    def _costs_not_negative(self) -> Self:
        if any(value < 0 for value in self.components.values()):
            raise ValueError("commodity costs must not be negative")
        return self


class WorkforceConfig(ConfigModel):
    """S7 workforce assumptions. These are tunable modelling guesses."""

    days_per_month: int = Field(gt=0)
    overtime_capacity_coeff: float = Field(ge=0)
    overtime_wage_premium: float = Field(ge=1)
    base_annual_turnover: float = Field(ge=0)
    overtime_turnover_coeff: float = Field(ge=0)
    wage_reference: float = Field(gt=0)
    wage_turnover_coeff: float = Field(ge=0)
    hiring_cost_per_employee: float = Field(ge=0)
    productivity_churn_penalty: float = Field(ge=0)
    min_employees: int = Field(default=5, ge=1)


class RndConfig(ConfigModel):
    """S7 delayed R&D assumptions. These are tunable modelling guesses."""

    lag_days: int = Field(ge=0)
    effect_per_chf: float = Field(ge=0)
    quality_cap: float = Field(ge=0, le=1)
    daily_quality_decay: float = Field(ge=0)


class ReputationConfig(ConfigModel):
    """Feedback-link coefficients for bounded annual reputation adjustment."""

    reputation_adjust_speed: float = Field(default=0.3, ge=0, le=1)
    service_weight: float = Field(default=0.4, ge=0, le=1)
    quality_weight: float = Field(default=0.4, ge=0, le=1)
    wage_weight: float = Field(default=0.2, ge=0, le=1)
    price_volatility_penalty: float = Field(default=0.5, ge=0)
    price_volatility_floor: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="after")
    def _weights_must_sum_to_one(self) -> Self:
        total = self.service_weight + self.quality_weight + self.wage_weight
        if not isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"reputation weights must sum to 1.0 (got {total})")
        return self


class ReliabilityConfig(ConfigModel):
    """Feedback-link coefficient for earned supplier reliability."""

    reliability_adjust_speed: float = Field(default=0.4, ge=0, le=1)


class CapacityConfig(ConfigModel):
    """Feedback-link coefficients for overload-driven quality loss."""

    overload_utilization_threshold: float = Field(default=0.9, ge=0, le=1)
    overload_quality_penalty: float = Field(default=0.3, ge=0)


class PolicyConfig(ConfigModel):
    """Ordering-policy safety limits and supplier concentration."""

    max_order_demand_multiple: float = Field(default=6.0, ge=0)
    concentration: float = Field(default=4.0, ge=0)
    supplier_priority_boost: float = Field(default=2.0, ge=0)


class AdaptiveStrategyConfig(ConfigModel):
    """Bounds for deterministic, incremental annual strategy learning."""

    price_step_fraction: float = Field(default=0.01, gt=0, le=0.25)
    rnd_min_multiplier: float = Field(default=0.55, ge=0)
    rnd_max_multiplier: float = Field(default=1.80, ge=0)
    rnd_step_multiplier: float = Field(default=0.10, gt=0)
    safety_stock_min_days: int = Field(default=4, ge=0)
    safety_stock_max_days: int = Field(default=18, ge=0)
    max_hires_per_year: int = Field(default=3, ge=0)
    # Price competition: react to the rivals' average price on the own stage.
    competitive_pull: float = Field(default=0.0, ge=0, le=1)
    undercut_fraction: float = Field(default=0.0, ge=0, le=0.5)
    share_loss_trigger: float = Field(default=0.01, ge=0)
    max_price_step_fraction: float = Field(default=0.0, ge=0, le=0.5)

    @model_validator(mode="after")
    def _bounds_are_ordered(self) -> Self:
        if self.rnd_min_multiplier > self.rnd_max_multiplier:
            raise ValueError("rnd_min_multiplier must not exceed rnd_max_multiplier")
        if self.safety_stock_min_days > self.safety_stock_max_days:
            raise ValueError("safety_stock_min_days must not exceed safety_stock_max_days")
        return self


class SupplierScoreWeights(ConfigModel):
    price: float
    reliability: float
    quality: float
    reputation: float
    lead_time: float
    capacity: float

    @model_validator(mode="after")
    def _weights_must_sum_to_one(self) -> Self:
        total = (
            self.price
            + self.reliability
            + self.quality
            + self.reputation
            + self.lead_time
            + self.capacity
        )
        if not isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"supplier score weights must sum to 1.0 (got {total})")
        return self


class MarketConfig(ConfigModel):
    unit_scale: UnitScaleConfig
    demand: DemandConfig
    price: PriceConfig
    stage_prices: dict[str, StagePriceConfig]
    simulation: SimulationConfig
    logistics: LogisticsConfig
    costs: CostConfig
    fixed_costs: FixedCostConfig = Field(default_factory=FixedCostConfig)
    commodities: CommodityConfig = Field(default_factory=CommodityConfig)
    workforce: WorkforceConfig
    rnd: RndConfig
    reputation: ReputationConfig
    reliability: ReliabilityConfig = Field(default_factory=ReliabilityConfig)
    capacity: CapacityConfig = Field(default_factory=CapacityConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    adaptive_strategy: AdaptiveStrategyConfig = Field(default_factory=AdaptiveStrategyConfig)
    demand_attractiveness_weights: AttractivenessWeights
    supplier_score_weights: SupplierScoreWeights
    bankruptcy: BankruptcyConfig = Field(default_factory=BankruptcyConfig)
    start_variation: StartVariationConfig = Field(default_factory=StartVariationConfig)
    events: MarketEventsConfig = Field(default_factory=MarketEventsConfig)

    @model_validator(mode="after")
    def _validate_stage_prices(self) -> Self:
        expected = {"factory", "distributor", "wholesaler", "retailer"}
        if set(self.stage_prices) != expected:
            raise ValueError(
                "stage_prices must contain exactly: " + ", ".join(sorted(expected))
            )
        for stage, band in self.stage_prices.items():
            if band.min < self.price.min or band.max > self.price.max:
                raise ValueError(
                    f"stage_prices.{stage} must be within the global price bounds"
                )
        return self

    @property
    def total_simulation_days(self) -> int:
        """Return the configured simulation horizon in days."""

        return self.simulation.years * self.simulation.days_per_year


def load_market_config(path: str | Path | None = None) -> MarketConfig:
    """Load and validate a market configuration YAML file.

    The default path is anchored to this module so loading is independent of
    the process's current working directory.
    """

    config_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parent / "config" / "market.yaml"
    )
    with config_path.open(encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    if not isinstance(data, dict):
        raise ValueError(f"market config must contain a YAML mapping: {config_path}")
    return MarketConfig.model_validate(data)
