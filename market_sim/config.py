"""Typed configuration for the Swiss beer market simulation."""

from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Literal, Self

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
    # Summer seasonality of total demand.
    seasonal_amplitude: float = Field(default=0.25, ge=0, lt=1)
    seasonal_phase_days: float = 90.0


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


class MarketEventTypeConfig(ConfigModel):
    """One reusable yearly event definition and its effect handler."""

    type: str = Field(min_length=1)
    enabled: bool = True
    probability_per_year: float = Field(ge=0, le=1)
    duration_days: int = Field(gt=0)
    strength: float = Field(gt=0)
    effect_handler: Literal[
        "demand_multiplier", "material_cost_multiplier", "firm_recall",
        "stage_capacity_multiplier", "wage_push",
    ]
    # Phase 3: stage hit by a capacity event.
    stage: str | None = None
    reputation_strength: float = Field(default=0.0, ge=0, le=1)
    cost: float = Field(default=0.0, ge=0)


class MarketEventsConfig(ConfigModel):
    """Generic yearly events, evaluated in the configured fixed order."""

    enabled: bool = True
    types: list[MarketEventTypeConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _event_types_must_be_unique(self) -> Self:
        names = [event.type for event in self.types]
        if len(names) != len(set(names)):
            raise ValueError("market event types must be unique")
        return self


class SupplierDiscoveryConfig(ConfigModel):
    """Runtime discovery of active firms on the immediately upstream stage."""

    enabled: bool = True


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
    # Open orders beyond this many days of supplier capacity are cancelled so
    # customers can reorder elsewhere; None keeps orders queued forever.
    max_backlog_days: float | None = Field(default=None, gt=0)


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


class MarketEntryConfig(ConfigModel):
    enabled: bool = False
    base_probability: float = Field(default=0.08, ge=0, le=1)
    # Phase 6: a stage with less capacity than this multiple of daily demand gets a
    # full-size entrant for sure (0 switches the rule off).
    shortage_capacity_ratio: float = Field(default=0.0, ge=0)
    margin_threshold: float = 0.05
    margin_slope: float = Field(default=2.0, ge=0)
    max_probability: float = Field(default=0.5, ge=0, le=1)
    # Yearly chance per stage that a small firm is founded regardless of margin and capacity.
    founding_probability: dict[str, float] = Field(default_factory=dict)
    # Share of retail foundings that open a restaurant instead of a store.
    restaurant_founding_share: float = Field(default=0.5, ge=0, le=1)
    max_firms_per_stage: dict[str, int] = Field(default_factory=dict)
    start_cash_fraction: float = Field(default=0.5, ge=0)
    start_capacity_fraction: float = Field(default=0.5, gt=0, le=1)
    start_reputation: tuple[float, float] = (0.4, 0.5)
    start_quality_fraction: float = Field(default=0.9, ge=0, le=1)
    names: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _entry_bounds(self) -> Self:
        if not 0 <= self.start_reputation[0] <= self.start_reputation[1] <= 1:
            raise ValueError("start_reputation must be ordered within [0, 1]")
        if not set(self.founding_probability) <= {"retailer", "wholesaler", "distributor", "factory"}:
            raise ValueError("founding_probability keys must be stages")
        if any(not 0 <= p <= 1 for p in self.founding_probability.values()):
            raise ValueError("founding_probability values must lie within [0, 1]")
        if self.enabled:
            stages = {"retailer", "wholesaler", "distributor", "factory"}
            if not stages <= set(self.names) or set(self.max_firms_per_stage) != stages:
                raise ValueError("entry names and limits must cover all stages")
            if any(n < 1 for n in self.max_firms_per_stage.values()) or any(not n for n in self.names.values()):
                raise ValueError("entry limits and name lists must be nonempty")
        return self


class CentralBankConfig(ConfigModel):
    enabled: bool = False
    start_rate: float = 0.01
    target_inflation: float = 0.01
    neutral_real_rate: float = 0.0
    inflation_weight: float = Field(default=0.5, ge=0)
    gap_weight: float = Field(default=0.5, ge=0)
    min_rate: float = -0.0075
    max_rate: float = 0.08
    max_step: float = Field(default=0.005, ge=0)
    gap_cap: float = Field(default=0.10, ge=0, le=1)
    gap_smoothing: float = Field(default=0.5, ge=0, le=1)
    demand_effect: float = Field(default=0.5, ge=0)
    demand_effect_cap: float = Field(default=0.05, ge=0, le=1)
    inflation_effect: float = Field(default=0.05, ge=0)
    inflation_effect_cap: float = Field(default=0.005, ge=0)

    @model_validator(mode="after")
    def _rate_bounds(self) -> Self:
        if not self.min_rate <= self.start_rate <= self.max_rate:
            raise ValueError("central bank start_rate must be within min_rate and max_rate")
        return self


class CommercialBankConfig(ConfigModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    margin: float = Field(default=0.02, ge=0)


class BankingConfig(ConfigModel):
    enabled: bool = False
    banks: list[CommercialBankConfig] = Field(default_factory=lambda: [
        CommercialBankConfig(id="B1", name="Helvetia Bank", margin=0.015),
        CommercialBankConfig(id="B2", name="Alpenbank", margin=0.02),
        CommercialBankConfig(id="B3", name="Mittelland Kantonalbank", margin=0.025),
    ], min_length=1)
    start_equity_fraction: float = Field(default=0.15, ge=0)
    # Share of a defaulted debt the bank loses; the rest is recovered from the bankrupt estate.
    loss_given_default: float = Field(default=1.0, ge=0, le=1)
    max_accounts: int = Field(default=2, ge=1, le=2)
    operating_cost_rate: float = Field(default=0.003, ge=0)
    payout_ratio: float = Field(default=0.5, ge=0, le=1)
    target_capital_ratio: float = Field(default=0.15, ge=0)
    min_capital_ratio: float = Field(default=0.10, gt=0, le=1)
    # Firms at their credit line may not buy goods either (strict credit crunch); investments are always blocked.
    block_purchases: bool = False
    second_account_enabled: bool = True
    second_account_share: float = Field(default=0.5, gt=0, lt=1)
    interest_weight: float = Field(default=1.0, ge=0)
    safety_weight: float = Field(default=1.0, ge=0)
    random_weight: float = Field(default=0.05, ge=0)
    # Phase 16: failure (negative equity), deposit insurance and new banks.
    insured_share: float = Field(default=0.3, ge=0, le=1)
    # Share of excess reserves exempt from a negative SNB rate (Freibetrag, as 2015-2022).
    reserve_exemption: float = Field(default=0.0, ge=0, le=1)
    max_failure_rounds: int = Field(default=3, ge=1)
    entry_enabled: bool = False
    max_banks: int = Field(default=6, ge=1)
    entry_probability: float = Field(default=0.3, ge=0, le=1)
    entry_min_roe: float = 0.08
    entry_rejections: int = Field(default=5, ge=0)
    entry_names: list[str] = Field(default_factory=lambda: [
        "Zürcher Privatbank", "Gotthard Bank", "Rhein Bank", "Léman Banque"])
    entry_margin: float = Field(default=0.02, ge=0)

    @model_validator(mode="after")
    def _unique_banks(self) -> Self:
        if len({bank.id for bank in self.banks}) != len(self.banks):
            raise ValueError("bank ids must be unique")
        return self


class BankConfig(ConfigModel):
    enabled: bool = False
    base_rate: float = Field(default=0.03, ge=0)
    loan_margin: float = Field(default=0.02, ge=0)
    deposit_spread: float = Field(default=0.005, ge=0)
    risk_premium_per_loss_year: float = Field(default=0.01, ge=0)
    leverage_premium: float = Field(default=0.04, ge=0)
    max_rate: float = Field(default=0.15, ge=0)
    deposit_rate: float = Field(default=0.005, ge=0)
    negative_interest_enabled: bool = True
    deposit_threshold_revenue_fraction: float = Field(default=0.5, ge=0)
    deposit_threshold_min: float = Field(default=50_000_000, ge=0)
    negative_rate: float = Field(default=0.0075, ge=0)
    credit_limit_revenue_fraction: float = Field(default=0.25, ge=0)
    credit_limit_initial_cash_fraction: float = Field(default=1.0, ge=0)
    credit_limit_min: float = Field(default=0.0, ge=0)
    # Phase 3: an insolvent firm protected by min_firms_per_stage is restructured:
    # the bank writes its debt off and its reputation suffers.
    restructuring: bool = False
    restructuring_reputation_hit: float = Field(default=0.10, ge=0, le=1)


class StrategyChangeConfig(ConfigModel):
    enabled: bool = False
    bad_years_trigger: int = Field(default=2, ge=1)
    explore_probability: float = Field(default=0.2, ge=0, le=1)
    imitation_window_years: int = Field(default=3, ge=1)
    lockout_years: int = Field(default=4, ge=0)
    switch_cost_fraction_of_revenue: float = Field(default=0.02, ge=0)
    reputation_dip: float = Field(default=0.05, ge=0, le=1)
    # A year in the bottom third of the stage also counts as bad, not only a loss.
    count_bottom_third: bool = True
    # Imitate only when the best archetype beats the own one by this return gap.
    min_return_gap: float = Field(default=0.0, ge=0)
    stages: list[str] = Field(default_factory=lambda: ["retailer", "wholesaler", "distributor", "factory"])


class ConsumerWeights(ConfigModel):
    price: float = Field(ge=0, le=1)
    quality: float = Field(ge=0, le=1)
    brand_reputation: float = Field(ge=0, le=1)
    store_reputation: float = Field(ge=0, le=1)
    availability: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _normalized(self) -> Self:
        if not isclose(sum(self.model_dump().values()), 1.0, abs_tol=1e-3):
            raise ValueError("consumer weights must sum to 1")
        return self


class ConsumerClass(ConfigModel):
    name: str
    persons: int = Field(gt=0)
    units_per_person_per_year: float = Field(gt=0)
    max_price: float = Field(gt=0)
    age_group: str | None = None
    income_level: int | None = None
    weights: ConsumerWeights


class ConsumersConfig(ConfigModel):
    """Phase 2: consumer classes with a willingness to pay (consumers.yaml)."""

    wtp_slope: float = Field(default=0.6, ge=0, le=2)
    classes: list[ConsumerClass]

    @model_validator(mode="after")
    def _unique_names(self) -> Self:
        if len({c.name for c in self.classes}) != len(self.classes):
            raise ValueError("consumer class names must be unique")
        return self


class BrandDefinition(ConfigModel):
    id: str
    name: str
    owner: str
    positioning: Literal["premium", "standard", "cheap"]
    traits: list[str] = Field(default_factory=list)
    # Phase 4: category and maturation time (wine) of the brand.
    category: str = "beer"
    maturation_days: int = Field(default=0, ge=0)


class BrandsConfig(ConfigModel):
    """Phase 2: brands that carry product reputation (brands.yaml)."""

    reputation_speed: float = Field(default=0.3, ge=0, le=1)
    quality_weight: float = Field(default=0.6, ge=0, le=1)
    production_share_floor: float = Field(default=0.1, ge=0, le=1)
    quality_offsets: dict[str, float]
    price_factors: dict[str, float]
    entrant_positioning: dict[str, str]
    # Phase 3: trait of a new brewery's brand by archetype (it also adopts the current trend).
    entrant_traits: dict[str, list[str]] = Field(default_factory=dict)
    brands: list[BrandDefinition]


class CategoryConfig(ConfigModel):
    name: str
    # Price and cost level of one unit relative to beer (all units are standard drinks).
    value_factor: float = Field(gt=0)
    # Consumption relative to beer; beer is 1.0.
    relative_volume: float = Field(gt=0)
    # Share multiplier per income level above the middle (wine rises with income).
    income_tilt: float = Field(default=1.0, gt=0)


class ImportConfig(ConfigModel):
    cost_factor: float = Field(default=0.85, gt=0)
    tariff: float = Field(default=0.05, ge=0)
    lead_days: int = Field(default=10, ge=1)


class ExportConfig(ConfigModel):
    enabled: bool = True
    # Foreign demand per day as a share of domestic demand of that category.
    share: dict[str, float] = Field(default_factory=dict)
    fx_elasticity: float = Field(default=1.5, ge=0)
    quality_threshold: float = Field(default=0.6, ge=0, le=1)
    world_price_factor: float = Field(default=1.0, gt=0)


class CategoriesConfig(ConfigModel):
    """Phase 4: beer, wine and spirits with a fixed total need, imports and exports."""

    enabled: bool = False
    categories: list[CategoryConfig] = Field(default_factory=list)
    substitution: float = Field(default=0.5, ge=0, le=1)
    downstream_capacity_factor: float = Field(default=1.0, gt=0)
    # Handling of a mixed beverage range costs more per unit than pure beer.
    handling_cost_factor: float = Field(default=1.0, gt=0)
    retailer_bias: dict[str, dict[str, float]] = Field(default_factory=dict)
    bias_weight: float = Field(default=0.3, ge=0, le=1)
    harvest_day: int = Field(default=270, ge=0)
    yield_sd: float = Field(default=0.15, ge=0)
    vintage_quality_slope: float = Field(default=0.3, ge=0)
    wine_forecast_buffer: float = Field(default=1.1, gt=0)
    fx_start: float = Field(default=1.0, gt=0)
    fx_sd: float = Field(default=0.06, ge=0)
    fx_reversion: float = Field(default=0.3, ge=0, le=1)
    imports: ImportConfig = Field(default_factory=ImportConfig)
    exports: ExportConfig = Field(default_factory=ExportConfig)


class RegionConfig(ConfigModel):
    name: str
    population_share: float = Field(gt=0)
    # Map position in km (Swiss grid, rounded).
    x: float
    y: float


class GeographyConfig(ConfigModel):
    """Phase 5: regions, transport, own fleet or transport service, expansion and sites."""

    enabled: bool = False
    regions: list[RegionConfig] = Field(default_factory=list)
    road_factor: float = Field(default=1.25, gt=0)
    local_km: float = Field(default=20.0, ge=0)
    # Real CHF per sim-unit and km.
    own_rate: float = Field(default=1.0, ge=0)
    service_rate: float = Field(default=1.4, ge=0)
    damage_probability: float = Field(default=0.01, ge=0, le=1)
    damage_share: float = Field(default=0.05, ge=0, le=1)
    risk_aversion: float = Field(default=2.0, ge=0)
    fleet_cost_per_day: float = Field(default=3000.0, ge=0)
    fuel_volatility: float = Field(default=0.10, ge=0)
    km_per_lead_day: float = Field(default=100.0, gt=0)
    # Shoppers prefer nearby stores: a region counts 1 / (1 + km / travel_km) for a store.
    travel_km: float = Field(default=40.0, gt=0)
    build_cost_per_capacity_unit: dict[str, float] = Field(default_factory=dict)
    build_days: dict[str, int] = Field(default_factory=dict)
    depreciation_years: int = Field(default=10, ge=1)
    expand_utilization: float = Field(default=0.9, ge=0, le=1.01)
    stage_utilization_min: float = Field(default=0.85, ge=0, le=1.01)
    expand_fraction: float = Field(default=0.2, gt=0)
    cash_cover: float = Field(default=1.5, ge=0)
    site_fraction: float = Field(default=0.3, gt=0)
    site_coverage_gap: float = Field(default=0.7, gt=0)


class OffenceConfig(ConfigModel):
    name: str
    # wage: pay less than agreed; material: cheaper, unsafe ingredients; tax: hide profit.
    kind: Literal["wage", "material", "tax"]
    benefit: float = Field(gt=0, lt=1)
    detection_probability: float = Field(ge=0, le=1)
    fine_fixed: float = Field(default=0.0, ge=0)
    fine_revenue_share: float = Field(default=0.0, ge=0)
    reputation_hit: float = Field(default=0.0, ge=0, le=1)


class StateConfig(ConfigModel):
    """Phase 6: taxes, offences with hidden detection and fines, poisoning, takeovers, antitrust."""

    enabled: bool = False
    reputation_value_factor: float = Field(default=0.5, ge=0)
    # Share of firms that weigh offences at all (fixed per firm); the others stay honest.
    willing_share: float = Field(default=1.0, ge=0, le=1)
    profit_tax: float = Field(default=0.15, ge=0, le=1)
    offences: list[OffenceConfig] = Field(default_factory=list)
    # Firms start with guesses between true value x e^-spread and x e^spread.
    belief_spread: float = Field(default=1.0, ge=0)
    aversion: float = Field(default=1.0, ge=0)
    learning_rate: float = Field(default=0.3, ge=0, le=1)
    public_learning: float = Field(default=0.2, ge=0, le=1)
    poisoning_probability: float = Field(default=0.03, ge=0, le=1)
    poisoning_deaths: int = Field(default=40, ge=0)
    poisoning_sick: int = Field(default=1500, ge=0)
    fear_strength: float = Field(default=0.15, ge=0, le=1)
    fear_half_life_years: float = Field(default=1.0, gt=0)
    category_reputation_hit: float = Field(default=0.2, ge=0, le=1)
    distress_fraction: float = Field(default=0.6, ge=0)
    distress_loss_years: int = Field(default=2, ge=1)
    price_per_capacity_unit: float = Field(default=1_500_000.0, ge=0)
    cash_cover: float = Field(default=1.5, ge=0)
    max_takeovers_per_stage: int = Field(default=1, ge=0)
    block_share: float = Field(default=0.35, ge=0, le=1)
    breakup_share: float = Field(default=0.5, ge=0, le=1)
    breakup_fraction: float = Field(default=0.3, gt=0, lt=1)


class ResearchProjectConfig(ConfigModel):
    name: str
    selection_weight: float = Field(default=1.0, gt=0)
    # productivity: more output per employee; cost_reduction: cheaper raw materials;
    # new_brand: a premium brand; alkoholfrei: an alcohol-free beer brand.
    # Phase 24: reputation (+ points), awareness (store known better), margin (restaurant
    # markup x (1 + effect)), maturation (wine matures effect share faster).
    kind: Literal["productivity", "cost_reduction", "new_brand", "alkoholfrei",
                  "component_reduction", "transport_efficiency", "storage_automation", "robotics",
                  "reputation", "awareness", "margin", "maturation"]
    enabled: bool = True
    component: Literal["malt", "hops", "packaging", "energy"] | None = None
    cost: float = Field(gt=0)
    duration_days: int = Field(gt=0)
    success_probability: float = Field(ge=0, le=1)
    effect: float = Field(default=0.0, ge=0)
    stages: list[str] = Field(default_factory=lambda: ["retailer", "wholesaler", "distributor", "factory"])

    @model_validator(mode="after")
    def validate_effect(self) -> Self:
        if self.kind == "component_reduction" and self.component is None:
            raise ValueError("component_reduction requires a component")
        if self.kind in ("component_reduction", "transport_efficiency", "storage_automation", "robotics",
                         "maturation") and self.effect >= 1:
            raise ValueError("reduction effects must be smaller than one")
        return self


class ResearchStageConfig(ResearchProjectConfig):
    """Phase 24: one stage of a research tree: research (cost x, uncertain), then implementation."""

    requires: list[str] = Field(default_factory=list)
    complexity: Literal["simple", "medium", "complex"] = "simple"
    implementation_cost: float = Field(default=0.0, ge=0)
    implementation_days: int = Field(default=90, gt=0)
    # Branch of the tree that archetypes may prefer, e.g. "automation" or "marke".
    branch: str = ""
    # Only firms of these product categories (empty = all); requirements a firm cannot
    # reach because of this restriction count as fulfilled.
    categories: list[str] = Field(default_factory=list)
    # Phase 25: the first firm to research this stage may patent it.
    patentable: bool = False


class PatentsConfig(ConfigModel):
    """Phase 25: patents on the first research success of patentable stages (no licences)."""

    enabled: bool = False
    min_years: int = Field(default=3, ge=1)
    max_years: int = Field(default=5, ge=1)
    # Fee = (base_fee + fee_per_year x years) x price index, paid once to the state.
    base_fee: float = Field(default=2_000_000.0, ge=0)
    fee_per_year: float = Field(default=1_000_000.0, ge=0)
    cash_cover: float = Field(default=2.0, ge=0)
    # Cash above this multiple of the longest fee: the firm patents for the longest term.
    rich_cash_multiple: float = Field(default=20.0, ge=0)
    long_archetypes: list[str] = Field(default_factory=lambda: ["premium"])
    short_archetypes: list[str] = Field(default_factory=lambda: ["low_cost"])

    @model_validator(mode="after")
    def validate_years(self) -> Self:
        if self.min_years > self.max_years:
            raise ValueError("min_years must not exceed max_years")
        return self


class ResearchConfig(ConfigModel):
    """Phase 7: expensive research projects with an uncertain outcome."""

    enabled: bool = False
    start_probability: float = Field(default=0.3, ge=0, le=1)
    cash_cover: float = Field(default=3.0, ge=0)
    projects: list[ResearchProjectConfig] = Field(default_factory=list)
    preferences: dict[str, list[str]] = Field(default_factory=dict)
    # Phase 24: one research tree per sector (factory, distributor, wholesaler, retailer,
    # restaurant) instead of the loose projects above.
    trees_enabled: bool = False
    trees: dict[str, list[ResearchStageConfig]] = Field(default_factory=dict)
    # Research discount for followers once another firm succeeded, by complexity.
    follower_discount: dict[str, float] = Field(
        default_factory=lambda: {"simple": 0.75, "medium": 0.5, "complex": 0.25})
    # Archetype -> preferred branches of the trees.
    branch_preferences: dict[str, list[str]] = Field(default_factory=dict)


class MarketingConfig(ConfigModel):
    """Phase 10: advertising builds awareness of brands and stores, which fades again."""

    enabled: bool = False
    # Yearly budget as a share of last year's revenue, by archetype.
    budget_share: dict[str, float] = Field(default_factory=dict)
    # Awareness gained per real CHF spent (diminishing: 1 - exp(-spend * effect)).
    effect_per_chf: float = Field(default=1e-8, ge=0)
    decay_per_year: float = Field(default=0.3, ge=0, le=1)
    start_awareness: float = Field(default=0.5, ge=0, le=1)
    brand_weight: float = Field(default=0.4, ge=0)
    store_weight: float = Field(default=0.3, ge=0)
    # How strongly each age group reacts to advertising.
    age_sensitivity: dict[str, float] = Field(default_factory=dict)


class RestaurantConfig(ConfigModel):
    """Phase 10: restaurants and bars as a channel next to the stores."""

    enabled: bool = False
    # Share of consumption out of home, before age and income adjustments.
    out_of_home_share: float = Field(default=0.15, ge=0, le=1)
    age_factor: dict[str, float] = Field(default_factory=dict)
    income_step: float = Field(default=0.1, ge=0)
    # Restaurant prices are store prices times this markup; guests accept it.
    markup: float = Field(default=3.0, gt=0)
    # Service, rent and kitchen cost as a share of restaurant revenue.
    service_cost_share: float = Field(default=0.6, ge=0, lt=1)
    fixed_cost_factor: float = Field(default=1.6, gt=0)
    # Share of unmet out-of-home demand that buys in a store instead.
    spill_to_stores: float = Field(default=0.5, ge=0, le=1)
    # Competition between the channels: how strongly the out-of-home share reacts when
    # restaurants are dearer or cheaper relative to stores than the usual markup.
    price_elasticity: float = Field(default=1.0, ge=0)
    # Part of the out-of-home share that goes out regardless of price (company, food, events).
    loyal_share: float = Field(default=0.5, ge=0, le=1)


class StockMarketConfig(ConfigModel):
    enabled: bool = False
    # Phase 17: all active firms trade from this simulation year on (IPO via a bank is a TODO).
    tradable_from_year: int = Field(default=5, ge=1)
    shares_per_firm: int = Field(default=1_000_000, gt=0)
    base_multiple: float = Field(default=8.0, gt=0)
    rate_sensitivity: float = Field(default=10.0, ge=0)
    min_multiple: float = Field(default=3.0, gt=0)
    max_multiple: float = Field(default=15.0, gt=0)
    reversion: float = Field(default=0.01, ge=0, le=1)
    volatility: float = Field(default=0.015, ge=0)
    revalue_days: int = Field(default=91, ge=1)
    event_shocks: dict[str, float] = Field(default_factory=lambda: {
        "poisoning": -0.5, "firm_recall": -0.15, "recall": -0.15, "offence_detected": -0.1,
        "rnd_success": 0.1, "restructuring": -0.3, "patent_granted": 0.05})
    index_base: float = Field(default=1000.0, gt=0)
    # Phase 23: ETFs as display-only baskets (not tradable yet), chain-linked like the index.
    etfs_enabled: bool = True
    etf_groups: list[Literal["region", "category", "stage"]] = Field(
        default_factory=lambda: ["region", "category", "stage"])
    etf_weighting: Literal["market_cap", "equal"] = "market_cap"
    etf_base: float = Field(default=100.0, gt=0)


class HoldingsConfig(ConfigModel):
    """Phase 10: minority stakes in other firms instead of full takeovers."""

    enabled: bool = False
    min_stake: float = Field(default=0.1, gt=0, lt=1)
    max_stake: float = Field(default=0.49, gt=0, lt=1)
    buy_probability: float = Field(default=0.3, ge=0, le=1)
    # Buy only with cash above this multiple of the stake price.
    cash_cover: float = Field(default=2.0, ge=0)
    # Value of a firm = profit_multiple x mean profit of the last two years + positive cash.
    profit_multiple: float = Field(default=4.0, ge=0)
    payout_ratio: float = Field(default=0.5, ge=0, le=1)
    sell_after_loss_years: int = Field(default=2, ge=1)
    # Phase 18: stakes below small_stake_limit are bought on the exchange through the owner's bank
    # (broker fee, shares in the bank's custody); larger stakes stay direct deals and may be credit-financed.
    via_bank: bool = False
    small_stake_limit: float = Field(default=0.10, gt=0, lt=1)
    broker_fee: float = Field(default=0.005, ge=0)
    control_premium: float = Field(default=0.2, ge=0)
    price_impact: float = Field(default=0.5, ge=0)
    # Stakes from this size count for antitrust like own market share.
    antitrust_stake: float = Field(default=0.25, ge=0, le=1)


class LawConfig(ConfigModel):
    name: str
    title_de: str
    kind: Literal["minimum_wage", "excise", "ad_ban", "packaging", "controls", "import_tariff"]
    probability_per_year: float = Field(ge=0, le=1)
    earliest_year: int = Field(default=5, ge=1)
    strength: float = 0.0
    category: str | None = None
    # KPIs watched to judge whether the law had a clear effect.
    watch: list[str] = Field(default_factory=list)


class LawsConfig(ConfigModel):
    """Phase 10: the state passes new laws; firms are not told what they do."""

    enabled: bool = False
    laws: list[LawConfig] = Field(default_factory=list)
    min_years_after: int = Field(default=3, ge=1)
    window_years: int = Field(default=5, ge=1)
    # An effect counts as clear when it exceeds this many standard deviations of the years before.
    clear_effect_sigma: float = Field(default=2.0, gt=0)


class LaborConfig(ConfigModel):
    """Phase 11: one pool of workers per region; scarcity raises wages and invites poaching."""

    enabled: bool = False
    # Pool at the start = employees of the region x (1 + slack); grows with the population.
    initial_slack: float = Field(default=0.10, ge=0)
    tight_threshold: float = Field(default=0.95, gt=0)
    wage_pressure: float = Field(default=0.5, ge=0)
    wage_relief: float = Field(default=0.05, ge=0)
    wage_index_min: float = Field(default=0.9, gt=0)
    wage_index_max: float = Field(default=1.5, gt=0)
    # Firms paying this much below the regional average lose this share of staff per year.
    poach_gap: float = Field(default=0.05, ge=0)
    poach_rate: float = Field(default=0.05, ge=0, le=1)


class OllamaConfig(ConfigModel):
    """Phase 12: language model for stories, the chronicle and the dashboard chat."""

    # "ollama" = local model, nothing leaves the machine; "api" = OpenAI-compatible API (e.g. SwissAI).
    provider: str = Field(default="ollama", pattern="^(ollama|api)$")
    host: str = "http://localhost:11434"
    story_model: str = "llama3.2:3b"
    chat_model: str = "llama3.2:3b"
    timeout_seconds: float = Field(default=180.0, gt=0)
    temperature: float = Field(default=0.3, ge=0, le=2)
    max_tokens: int = Field(default=400, gt=0)
    api_base_url: str = "https://api.swissai.svc.cscs.ch/v1"
    # Name of the environment variable holding the key; the key itself never goes into the repo.
    api_key_env: str = "SWISSAI_RESEARCH_API_KEY"
    api_story_model: str = "CSCS-Inference/zai-org/GLM-5.3"
    api_chat_model: str = "CSCS-Inference/zai-org/GLM-5.3"
    requests_per_minute: float = Field(default=14.0, gt=0)
    api_reasoning_effort: str = "low"


class TrendConfig(ConfigModel):
    name: str
    trait: str
    strength: float = Field(ge=0)
    age_groups: list[str] = Field(default_factory=list)


class LongRunConfig(ConfigModel):
    """Phase 3: inflation, real wage and productivity growth, population and trends."""

    enabled: bool = False
    inflation_mean: float = 0.01
    inflation_sd: float = 0.008
    inflation_min: float = -0.01
    inflation_max: float = 0.04
    real_wage_growth: float = 0.005
    productivity_growth: float = 0.005
    population_growth: dict[str, float] = Field(default_factory=dict)
    trend_years: tuple[int, int] = (3, 8)
    trend_transition_years: int = Field(default=2, ge=1)
    trends: list[TrendConfig] = Field(default_factory=list)


class PersonasConfig(ConfigModel):
    enabled: bool = True
    first_names: dict[str, list[str]] = Field(default_factory=dict)
    surnames: list[str] = Field(default_factory=list)
    age_ranges: dict[str, tuple[int, int]] = Field(default_factory=dict)
    income_ranges: dict[int, tuple[int, int]] = Field(default_factory=dict)
    jobs: dict[int, list[str]] = Field(default_factory=dict)
    priorities: dict[str, str] = Field(default_factory=dict)


class TraceabilityConfig(ConfigModel):
    enabled: bool = True
    exit_history_years: int = Field(default=5, ge=1, le=5)
    exit_drivers: int = Field(default=3, ge=1, le=3)


class MarketConfig(ConfigModel):
    personas: PersonasConfig = Field(default_factory=PersonasConfig)
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
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
    supplier_score_weights: SupplierScoreWeights
    bankruptcy: BankruptcyConfig = Field(default_factory=BankruptcyConfig)
    start_variation: StartVariationConfig = Field(default_factory=StartVariationConfig)
    events: MarketEventsConfig = Field(default_factory=MarketEventsConfig)
    supplier_discovery: SupplierDiscoveryConfig = Field(default_factory=SupplierDiscoveryConfig)
    market_entry: MarketEntryConfig = Field(default_factory=MarketEntryConfig)
    bank: BankConfig = Field(default_factory=BankConfig)
    banking: BankingConfig = Field(default_factory=BankingConfig)
    central_bank: CentralBankConfig = Field(default_factory=CentralBankConfig)
    strategy_change: StrategyChangeConfig = Field(default_factory=StrategyChangeConfig)
    consumers: ConsumersConfig | None = None
    brands: BrandsConfig | None = None
    long_run: LongRunConfig = Field(default_factory=LongRunConfig)
    categories: CategoriesConfig = Field(default_factory=CategoriesConfig)
    geography: GeographyConfig = Field(default_factory=GeographyConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    patents: PatentsConfig = Field(default_factory=PatentsConfig)
    marketing: MarketingConfig = Field(default_factory=MarketingConfig)
    restaurants: RestaurantConfig = Field(default_factory=RestaurantConfig)
    holdings: HoldingsConfig = Field(default_factory=HoldingsConfig)
    stock_market: StockMarketConfig = Field(default_factory=StockMarketConfig)
    laws: LawsConfig = Field(default_factory=LawsConfig)
    labor: LaborConfig = Field(default_factory=LaborConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)

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
    # Phase 2: consumer classes and brands live in their own files next to market.yaml.
    for key in ("consumers", "brands", "personas"):
        side_file = config_path.parent / f"{key}.yaml"
        if key not in data and side_file.exists():
            with side_file.open(encoding="utf-8") as handle:
                data[key] = yaml.safe_load(handle)
    return MarketConfig.model_validate(data)
