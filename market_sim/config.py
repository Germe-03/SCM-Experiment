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


class PriceConfig(ConfigModel):
    base: float
    min: float
    max: float

    @model_validator(mode="after")
    def _prices_must_be_ordered(self) -> Self:
        if not self.min <= self.base <= self.max:
            raise ValueError("price must satisfy min <= base <= max")
        return self


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
    lead_time: float
    capacity: float

    @model_validator(mode="after")
    def _weights_must_sum_to_one(self) -> Self:
        total = (
            self.price
            + self.reliability
            + self.quality
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
    simulation: SimulationConfig
    logistics: LogisticsConfig
    costs: CostConfig
    workforce: WorkforceConfig
    rnd: RndConfig
    reputation: ReputationConfig
    demand_attractiveness_weights: AttractivenessWeights
    supplier_score_weights: SupplierScoreWeights

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
