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

    @model_validator(mode="after")
    def _elasticity_bounds_must_be_ordered(self) -> Self:
        if self.elasticity_min_mult > self.elasticity_max_mult:
            raise ValueError("elasticity_min_mult must not exceed elasticity_max_mult")
        return self


class BankruptcyConfig(ConfigModel):
    """P4b fix: centrally configured market exit policy."""

    enabled: bool = True
    cash_threshold: float = -100_000_000.0
    min_years_before_exit: int = Field(default=1, ge=0)


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


class RndConfig(ConfigModel):
    """S7 delayed R&D assumptions. These are tunable modelling guesses."""

    lag_days: int = Field(ge=0)
    effect_per_chf: float = Field(ge=0)
    quality_cap: float = Field(ge=0, le=1)
    daily_quality_decay: float = Field(ge=0)


class ReputationConfig(ConfigModel):
    """S9 bounded annual reputation adjustment."""

    reputation_adjust_speed: float = Field(default=0.3, ge=0, le=1)


class PolicyConfig(ConfigModel):
    """Ordering-policy safety limits and supplier concentration."""

    max_order_demand_multiple: float = Field(default=6.0, ge=0)
    concentration: float = Field(default=4.0, ge=0)


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
    workforce: WorkforceConfig
    rnd: RndConfig
    reputation: ReputationConfig
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    demand_attractiveness_weights: AttractivenessWeights
    supplier_score_weights: SupplierScoreWeights
    bankruptcy: BankruptcyConfig = Field(default_factory=BankruptcyConfig)

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
