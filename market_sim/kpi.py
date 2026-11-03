"""Standalone S9 KPI helpers and reporting models."""

from __future__ import annotations

from statistics import variance

from pydantic import BaseModel, Field


def herfindahl_index(shares: list[float]) -> float:
    """Return the Herfindahl index for fractional market shares."""
    return max(0.0, min(1.0, sum(float(share) ** 2 for share in shares)))


def bullwhip_variance_ratio(orders: list[float], demand: list[float]) -> float:
    """Return sample variance(orders) / sample variance(demand)."""
    if len(demand) < 2 or variance(demand) == 0:
        return 1.0
    order_variance = variance(orders) if len(orders) >= 2 else 0.0
    return order_variance / variance(demand)


def service_level(served: int, demand: int) -> float:
    """Return the served fraction, treating no demand as fully served."""
    if demand <= 0:
        return 1.0
    return max(0.0, min(1.0, served / demand))


class AnnualReport(BaseModel):
    archetype: str = ""
    interest_cost: float = 0.0
    year: int
    firm_id: str
    revenue: float
    profit: float
    market_share: float = Field(ge=0, le=1)
    average_sell_price: float
    average_quality: float = Field(ge=0, le=1)
    stockout_days: int = Field(ge=0)
    lost_sales: int = Field(ge=0)
    employee_turnover: float = Field(ge=0)
    average_wage: float = Field(ge=0)
    reputation: float = Field(ge=0, le=1)
    capacity_utilization: float = Field(ge=0, le=1)
    supplier_reliability: dict[str, float]
    main_problems: list[str]


class SystemKPIs(BaseModel):
    year: int
    total_profit: float
    total_backlog: int = Field(ge=0)
    total_lost_sales: int = Field(ge=0)
    average_customer_price: float
    average_quality: float = Field(ge=0, le=1)
    market_concentration: float = Field(ge=0, le=1)
    bullwhip_ratio: float = Field(ge=0)
    service_level: float = Field(ge=0, le=1)
    # Experiment indicators (see README, section Experiment).
    margin_retailer: float = 0.0
    margin_wholesaler: float = 0.0
    margin_distributor: float = 0.0
    margin_factory: float = 0.0
    utilization_retailer: float = 0.0
    utilization_wholesaler: float = 0.0
    utilization_distributor: float = 0.0
    utilization_factory: float = 0.0
    market_share_movement: float = 0.0
    firms_with_loss: int = 0
    bankruptcies: int = 0
    market_entries: int = 0
    strategy_changes: int = 0
    price_index: float = 1.0
    population_index: float = 1.0
    trend: str = ""
    fx_rate: float = 1.0
    export_units: int = 0
    share_beer: float = 0.0
    share_wine: float = 0.0
    share_spirits: float = 0.0
    transport_cost: float = 0.0
    damaged_units: int = 0
    expansions: int = 0
    new_sites: int = 0
    firms_using_service: int = 0
    fuel_index: float = 1.0
    taxes: float = 0.0
    offences: int = 0
    offences_detected: int = 0
    fines: float = 0.0
    poisonings: int = 0
    fear: float = 0.0
    takeovers: int = 0
    takeovers_blocked: int = 0
    breakups: int = 0
    rnd_started: int = 0
    rnd_successes: int = 0
    rnd_failures: int = 0
    rnd_project_spend: float = 0.0
    rnd_running: int = 0
    interest_cost_retailer: float = 0.0
    interest_cost_wholesaler: float = 0.0
    interest_cost_distributor: float = 0.0
    interest_cost_factory: float = 0.0
    debt_retailer: float = 0.0
    debt_wholesaler: float = 0.0
    debt_distributor: float = 0.0
    debt_factory: float = 0.0
    active_firms_retailer: int = 0
    active_firms_wholesaler: int = 0
    active_firms_distributor: int = 0
    active_firms_factory: int = 0
    retailer_price_spread: float = 0.0


# German wording for the event log (events.csv and dashboard).
STAGE_DE = {"retailer": "Detailhandel", "wholesaler": "Grosshandel", "distributor": "Verteilung", "factory": "Hersteller"}
ARCHETYPE_DE = {"low_cost": "Discount", "standard": "Standard", "premium": "Premium",
                "reliable": "Zuverlässig", "growth": "Wachstum"}
TREND_DE = {"craft_welle": "Craft-Welle", "alkoholfrei": "Alkoholfrei", "sparwelle": "Sparwelle",
            "tradition": "Tradition", "wein_boom": "Wein-Boom"}
OFFENCE_DE = {"lohndumping": "Lohndumping", "pfusch": "Pfusch bei Rohstoffen",
              "steuerhinterziehung": "Steuerhinterziehung"}
REGION_DE = {"genfersee": "Genferseeregion", "bern": "Bern", "jura_freiburg": "Jura/Freiburg/Neuenburg",
             "nordwestschweiz": "Nordwestschweiz", "zuerich": "Zürich", "ostschweiz": "Ostschweiz",
             "zentralschweiz": "Zentralschweiz", "tessin": "Tessin"}
PROJECT_DE = {"prozessautomation": "Prozessautomation", "rezeptur_optimierung": "Rezeptur-Optimierung",
              "neue_marke": "Neue Marke", "alkoholfreies_bier": "Alkoholfreies Bier"}


def chf(value: float) -> str:
    """Swiss money format for event texts, e.g. 1'234'567 CHF."""
    return f"{value:,.0f} CHF".replace(",", "'")

