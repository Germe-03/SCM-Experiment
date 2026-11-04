"""S8 two-level simulation runner for the full market mode."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import random
from statistics import pstdev
from typing import Callable

from market_sim.decisions import DecisionLog, exit_analysis
from market_sim.personas import generate_personas
from market_sim.region_report import RegionReporter
from market_sim.longrun import LongRun
from market_sim.state import StateActor
from market_sim.research import ResearchLab
from market_sim.marketing import Marketing
from market_sim.holdings import Holdings
from market_sim.laws import LawBook, assess_laws
from market_sim.labor import LaborMarket
from market_sim.config import MarketConfig, MarketEventTypeConfig
from market_sim.environment import MarketEnvironment, MarketResult
from market_sim.kpi import ARCHETYPE_DE, REGION_DE, STAGE_DE, chf
from market_sim.kpi import (
    AnnualReport, SystemKPIs, bullwhip_variance_ratio, herfindahl_index,
    service_level,
)
from market_sim.models import STAGES, Firm, SupplyNetwork
from market_sim.policies import FirmPolicy, policy_for_firm
from market_sim.strategy import AnnualStrategy, FirmObservation


@dataclass(frozen=True)
class YearSummary:
    revenue: float
    profit: float
    avg_inventory: float
    avg_backlog: float
    lost_sales: int
    service_level: float
    avg_sell_price: float
    quality: float
    capacity_utilization: float
    cash: float
    market_share: float = 0.0
    market_share_change: float = 0.0


@dataclass(frozen=True)
class RunResult:
    years: int
    network: SupplyNetwork
    yearly_summaries: list[dict[str, YearSummary]]
    final_result: MarketResult
    annual_reports: list[dict[str, AnnualReport]]
    system_kpis: list[SystemKPIs]
    daily_series: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    days_total: int = 0
    financial_breakdown: dict[str, list[dict[str, float]]] = field(default_factory=dict)
    exits: dict[str, int] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)
    brand_reports: list[dict[str, object]] = field(default_factory=list)
    class_reports: list[dict[str, object]] = field(default_factory=list)
    rnd_reports: list[dict[str, object]] = field(default_factory=list)
    offence_ledger: list[dict[str, object]] = field(default_factory=list)
    holdings: list[dict[str, object]] = field(default_factory=list)
    laws: list[dict[str, object]] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    region_reports: list[dict] = field(default_factory=list)
    firm_locations: list[dict] = field(default_factory=list)
    personas: list[dict] = field(default_factory=list)
    exit_analysis: dict = field(default_factory=dict)


@dataclass
class RunState:
    """Cross-year loop state; together with the runner it is a full checkpoint."""

    year: int = 0
    global_day: int = 0
    summaries: list[dict[str, YearSummary]] = field(default_factory=list)
    annual_reports: list[dict[str, AnnualReport]] = field(default_factory=list)
    system_kpis: list[SystemKPIs] = field(default_factory=list)
    daily_series: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    financial_breakdown: dict[str, list[dict[str, float]]] = field(default_factory=dict)
    recent_demand: dict[str, list[int]] = field(default_factory=dict)
    recent_sales: dict[str, list[int]] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)
    main_supplier: dict[str, str] = field(default_factory=dict)
    market_entries: dict[int, int] = field(default_factory=dict)
    brand_reports: list[dict[str, object]] = field(default_factory=list)
    class_reports: list[dict[str, object]] = field(default_factory=list)


class ConsumerDemandGenerator:
    """Seeded total demand with annual seasonality; classes then decide who buys."""

    def __init__(
        self, mean: int, seed: int, *, days_per_year: int = 365,
        seasonal_amplitude: float = 0.0, seasonal_phase_days: float = 90.0,
    ) -> None:
        self.mean = max(0, int(mean))
        self.days_per_year = max(1, int(days_per_year))
        self.seasonal_amplitude = seasonal_amplitude
        self.seasonal_phase_days = seasonal_phase_days
        self._rng = random.Random(seed)
        # (first global day, last global day, factor) windows from market events.
        self.event_windows: list[tuple[int, int, float]] = []

    def seasonal_factor(self, global_day: int) -> float:
        factor = 1 + self.seasonal_amplitude * math.sin(
            2 * math.pi * ((global_day % self.days_per_year) - self.seasonal_phase_days)
            / self.days_per_year
        )
        return max(float.fromhex("0x1.0p-1022"), factor)

    def event_factor(self, global_day: int) -> float:
        factor = 1.0
        for first, last, multiplier in self.event_windows:
            if first <= global_day <= last:
                factor *= multiplier
        return factor

    def __call__(self, global_day: int) -> int:
        noise = self._rng.uniform(0.9, 1.1)
        effective = self.mean * self.seasonal_factor(global_day) * noise * self.event_factor(global_day)
        return max(0, round(effective))


class SimulationRunner:
    def __init__(
        self, network: SupplyNetwork, config: MarketConfig,
        policies: dict[str, FirmPolicy], seed: int,
    ) -> None:
        self.network = network
        self.config = config
        self.seed = seed
        self.decision_log = DecisionLog(config.traceability.enabled)
        self.region_reporter = RegionReporter(config.traceability.enabled)
        self.policies = policies
        firm_ids = {firm.id for firm in self._firms()}
        if set(policies) != firm_ids:
            raise ValueError("policies must contain exactly one policy per firm")
        demand = config.demand
        self.demand = ConsumerDemandGenerator(
            demand.daily_demand_units, seed,
            days_per_year=config.simulation.days_per_year,
            seasonal_amplitude=demand.seasonal_amplitude,
            seasonal_phase_days=demand.seasonal_phase_days,
        )
        self.env = MarketEnvironment(
            network, config=config,
            horizon=config.simulation.days_per_year * config.simulation.years,
            enforce_capacity=True, enable_workforce=True, enable_rnd=True,
            seed=seed,
        )
        self._event_rng = random.Random(f"events-{seed}")
        self.long_run = LongRun(self, seed)
        self._scale_for_categories()
        self.state_actor = StateActor(self, seed) if config.state.enabled else None
        self.lab = ResearchLab(self, seed) if config.research.enabled else None
        self._restaurant_templates = [f.model_copy(deep=True) for f in self._firms() if f.channel == "restaurant"]
        self._store_templates = [f.model_copy(deep=True) for f in self._firms()
                                 if f.stage == "retailer" and f.channel != "restaurant"]
        # Phase 10: marketing, minority stakes and new laws.
        self.marketing = Marketing(self) if config.marketing.enabled else None
        self.holdings = Holdings(self, seed) if config.holdings.enabled else None
        self.laws = LawBook(self, seed) if config.laws.enabled else None
        self.labor = LaborMarket(self) if config.labor.enabled else None
        self._phase1_rng = random.Random(f"phase1-{seed}")
        self._entry_counters = {stage: 0 for stage in STAGES}
        self._entry_cash = {
            stage: sum(f.cash for f in network.firms_in(stage)) / len(network.firms_in(stage))
            if network.firms_in(stage) else 0.0 for stage in STAGES
        }
        self._apply_start_variation(random.Random(f"start-{seed}"))
        self.strategies: dict[str, AnnualStrategy] = {}
        self.applied_prices: list[tuple[str, float, float, float]] = []
        self.exits: dict[str, int] = {}

    def run(self, years: int) -> RunResult:
        if years < 0:
            raise ValueError("years must be non-negative")
        return self.continue_run(self.start(), years)

    def start(self) -> RunState:
        """Reset the market and return the empty cross-year loop state."""
        self.env.reset()
        self.env.research = self.lab
        self.env.marketing = self.marketing
        self.exits = {}
        return RunState(
            daily_series={
                firm.id: {
                    "inventory": [], "backlog": [], "cash": [],
                    "cumulative_profit": [],
                    **({"consumer_units_sold": [], "demand_share": []}
                       if firm.stage == "retailer" else {}),
                }
                for firm in self._firms()
            },
            financial_breakdown={firm.id: [] for firm in self._firms()},
            recent_demand={firm.id: [] for firm in self._firms()},
            recent_sales={firm.id: [] for firm in self._firms()},
        )

    def continue_run(
        self, state: RunState, until_year: int,
        on_year_end: Callable[[SimulationRunner, RunState], None] | None = None,
    ) -> RunResult:
        """Simulate from ``state.year`` up to ``until_year`` and build the result."""
        if until_year < state.year:
            raise ValueError("until_year must not lie before the current state year")
        while state.year < until_year:
            self.run_year(state)
            if on_year_end is not None:
                on_year_end(self, state)
        return self.result(state)

    def result(self, state: RunState) -> RunResult:
        result = RunResult(
            decisions=list(self.decision_log.entries),
            region_reports=list(self.region_reporter.rows),
            firm_locations=list(self.region_reporter.locations),
            personas=generate_personas(self.config, self.seed, state.class_reports, state.brand_reports) if self.config.traceability.enabled else [],
            years=state.year, network=self.network, yearly_summaries=state.summaries,
            final_result=self.env.get_result(), annual_reports=state.annual_reports,
            system_kpis=state.system_kpis,
            daily_series=state.daily_series, days_total=state.global_day,
            financial_breakdown=state.financial_breakdown,
            exits=dict(self.exits), events=list(state.events),
            brand_reports=list(state.brand_reports), class_reports=list(state.class_reports),
            rnd_reports=list(self.lab.reports) if self.lab is not None else [],
            holdings=list(self.holdings.history) + self.holdings.snapshot(state.year) if self.holdings is not None else [],
            laws=assess_laws(self.laws.enacted, [k.model_dump() for k in state.system_kpis], self.config.laws)
            if self.laws is not None else [],
            offence_ledger=list(self.state_actor.offence_ledger) if self.state_actor is not None else [],
        )

        if self.config.traceability.enabled:
            object.__setattr__(result, "exit_analysis", exit_analysis(result, self.config.traceability.exit_history_years, self.config.traceability.exit_drivers))
        return result

    def _scale_for_categories(self) -> None:
        """Phase 4: wine and spirits add volume; trade stages and demand grow with it."""
        cats = self.config.categories
        if not (cats.enabled and cats.categories):
            return
        beer = next((c.relative_volume for c in cats.categories if c.name == "beer"), 1.0)
        self.demand.mean *= sum(c.relative_volume for c in cats.categories) / beer
        self.env.domestic_daily_demand = self.demand.mean
        # More staff, machines and rent, not a cheaper unit: wages and fixed costs grow too.
        factor = cats.downstream_capacity_factor
        for firm in self._firms():
            if firm.stage != "factory":
                firm.capacity = round(firm.capacity * factor)
                firm.machine_capacity = round(firm.machine_capacity * factor)
                firm.employees = max(1, round(firm.employees * factor))
        self.config.costs.handling_cost_per_unit *= cats.handling_cost_factor
        fixed = self.config.fixed_costs
        fixed.base_per_day = {
            stage: value * (factor if stage != "factory" else 1.0) for stage, value in fixed.base_per_day.items()
        }

    def _apply_start_variation(self, rng: random.Random) -> None:
        """Seeded start values: the same seed always yields the same market."""
        spread = self.config.start_variation
        if not (spread.cash_spread or spread.quality_spread or spread.reputation_spread):
            return
        for firm in self._firms():
            firm.cash *= 1 + rng.uniform(-spread.cash_spread, spread.cash_spread)
            firm.quality_level = self._clamp(
                firm.quality_level * (1 + rng.uniform(-spread.quality_spread, spread.quality_spread)), 0.05, 0.98)
            firm.reputation = self._clamp(
                firm.reputation * (1 + rng.uniform(-spread.reputation_spread, spread.reputation_spread)), 0.05, 0.98)

    def _draw_market_events(self, state: RunState) -> None:
        """Draw configured events and dispatch reusable effect handlers."""
        cfg = self.config.events
        rng = self._event_rng
        days = self.config.simulation.days_per_year
        year = state.year + 1
        event_rolls = [rng.random() for _ in cfg.types]
        # Keep auxiliary draws fixed and unconditional for seed compatibility.
        start_roll, target_roll = rng.random(), rng.random()
        self.env.material_cost_multiplier = 1.0
        self.env.capacity_windows = [w for w in self.env.capacity_windows if w[2] >= state.global_day]
        self.demand.event_windows = [w for w in self.demand.event_windows if w[1] >= state.global_day]
        handlers = {
            "demand_multiplier": self._event_demand_multiplier,
            "material_cost_multiplier": self._event_material_cost_multiplier,
            "firm_recall": self._event_firm_recall,
            "stage_capacity_multiplier": self._event_stage_capacity,
            "wage_push": self._event_wage_push,
        }
        if not cfg.enabled:
            return
        for definition, roll in zip(cfg.types, event_rolls):
            if definition.enabled and roll < definition.probability_per_year:
                handlers[definition.effect_handler](
                    definition, state, year, days, start_roll, target_roll,
                )

    def _event_demand_multiplier(
        self, event: MarketEventTypeConfig, state: RunState, year: int,
        days: int, start_roll: float, target_roll: float,
    ) -> None:
        first = round(days * 0.35 + start_roll * days * 0.2)
        self.demand.event_windows.append((
            state.global_day + first,
            state.global_day + first + event.duration_days - 1,
            event.strength,
        ))
        state.events.append({
            "year": year, "day": first + 1, "firm": "", "event": event.type,
            "details": f"Nachfrage ×{event.strength:g} während {event.duration_days} Tagen",
        })

    def _event_material_cost_multiplier(
        self, event: MarketEventTypeConfig, state: RunState, year: int,
        days: int, start_roll: float, target_roll: float,
    ) -> None:
        self.env.material_cost_multiplier *= event.strength
        state.events.append({
            "year": year, "day": 1, "firm": "", "event": event.type,
            "details": f"Rohstoffe ×{event.strength:g} während des ganzen Jahres",
        })

    def _event_stage_capacity(
        self, event: MarketEventTypeConfig, state: RunState, year: int,
        days: int, start_roll: float, target_roll: float,
    ) -> None:
        first = round(start_roll * max(1, days - event.duration_days))
        stage = event.stage or "factory"
        self.env.capacity_windows.append((
            stage, state.global_day + first, state.global_day + first + event.duration_days - 1, event.strength,
        ))
        state.events.append({
            "year": year, "day": first + 1, "firm": "", "event": event.type,
            "details": f"Kapazität {STAGE_DE.get(stage, stage)} ×{event.strength:g} während {event.duration_days} Tagen",
        })

    def _event_wage_push(
        self, event: MarketEventTypeConfig, state: RunState, year: int,
        days: int, start_roll: float, target_roll: float,
    ) -> None:
        for firm in self._firms():
            firm.initial_wage_level *= event.strength
            firm.wage_level *= event.strength
        state.events.append({
            "year": year, "day": 1, "firm": "", "event": event.type,
            "details": f"alle Löhne ×{event.strength:g}",
        })

    def _event_firm_recall(
        self, event: MarketEventTypeConfig, state: RunState, year: int,
        days: int, start_roll: float, target_roll: float,
    ) -> None:
        active = sorted(
            firm_id for firm_id, runtime in self.env.runtimes.items() if runtime.active
        )
        if not active:
            return
        firm_id = active[min(len(active) - 1, int(target_roll * len(active)))]
        firm = self.network.firm(firm_id)
        runtime = self.env.runtimes[firm_id]
        runtime.quality_level = self._clamp(runtime.quality_level - event.strength)
        firm.quality_level = self._clamp(firm.quality_level - event.strength)
        firm.reputation = self._clamp(firm.reputation - event.reputation_strength)
        runtime.fixed_cost += event.cost
        if self.env.brand_book is not None and firm.stage == "factory":
            self.env.brand_book.recall(firm_id, event.reputation_strength)
        state.events.append({
            "year": year, "day": 1, "firm": firm_id, "event": event.type,
            "details": f"Qualität −{event.strength:g}, Reputation −{event.reputation_strength:g}",
        })

    def add_firm(
        self, firm: Firm, state: RunState, policy: FirmPolicy | None = None,
    ) -> None:
        """Register a firm at a year boundary and align all result series."""

        if state.global_day != self.env.period:
            raise ValueError("run state and environment are not at the same day")
        if state.global_day % self.config.simulation.days_per_year:
            raise ValueError("firms can only be added at a year boundary")
        self.env.add_firm(firm)
        self.policies[firm.id] = policy or policy_for_firm(firm)
        zeros = [0.0] * state.global_day
        state.daily_series[firm.id] = {
            "inventory": list(zeros), "backlog": list(zeros), "cash": list(zeros),
            "cumulative_profit": list(zeros),
            **({"consumer_units_sold": list(zeros), "demand_share": list(zeros)}
               if firm.stage == "retailer" else {}),
        }
        empty_financial = {
            "revenue": 0.0, "purchase_cost": 0.0, "holding_cost": 0.0,
            "backlog_cost": 0.0, "wage_cost": 0.0, "hiring_cost": 0.0,
            "rnd_cost": 0.0, "handling_cost": 0.0, "fixed_cost": 0.0,
            "profit": 0.0, "cash": 0.0, "interest_cost": 0.0, "negative_interest_cost": 0.0,
        }
        state.financial_breakdown[firm.id] = [dict(empty_financial) for _ in range(state.year)]
        state.recent_demand[firm.id] = []
        state.recent_sales[firm.id] = []
        for index, summaries in enumerate(state.summaries):
            summaries[firm.id] = YearSummary(
                revenue=0.0, profit=0.0, avg_inventory=0.0, avg_backlog=0.0,
                lost_sales=0, service_level=1.0, avg_sell_price=firm.sell_price,
                quality=firm.quality_level, capacity_utilization=0.0, cash=0.0,
            )
            state.annual_reports[index][firm.id] = AnnualReport(
                year=index + 1, firm_id=firm.id, revenue=0.0, profit=0.0,
                market_share=0.0, average_sell_price=firm.sell_price,
                average_quality=firm.quality_level, stockout_days=0, lost_sales=0,
                employee_turnover=0.0, average_wage=firm.wage_level,
                reputation=firm.reputation, capacity_utilization=0.0,
                supplier_reliability={}, main_problems=["Not yet active"],
            )
        entry_year = state.year + 1
        state.market_entries[entry_year] = state.market_entries.get(entry_year, 0) + 1
        state.events.append({
            "year": entry_year, "day": 1, "firm": firm.id,
            "event": "market_entry", "details": f"neu im {STAGE_DE.get(firm.stage, firm.stage)}",
        })

    def run_year(self, state: RunState) -> None:
        """Simulate one full year and append its reports to ``state``."""
        year = state.year
        event_start = len(state.events)
        self.region_reporter.start_year(self)
        summaries, annual_reports, system_kpis = (
            state.summaries, state.annual_reports, state.system_kpis,
        )
        daily_series, financial_breakdown = state.daily_series, state.financial_breakdown
        recent_demand, recent_sales = state.recent_demand, state.recent_sales
        global_day = state.global_day
        previous = summaries[-1] if summaries else {}
        starts = self._financial_starts()
        financial_starts = self._financial_snapshot_all()
        history_starts = {
            firm.id: (len(self.env.inventory_history[firm.id]), len(self.env.backlog_history[firm.id]))
            for firm in self._firms()
        }
        price_totals = {firm.id: 0.0 for firm in self._firms()}
        daily_prices = {firm.id: [] for firm in self._firms()}
        retailer_lost = {firm.id: 0 for firm in self._firms()}
        retailer_served = {firm.id: 0 for firm in self._firms()}
        demand_series: list[float] = []
        factory_order_series: list[float] = []
        daily_quality = {firm.id: [] for firm in self._firms()}
        daily_turnover = {firm.id: [] for firm in self._firms()}
        utilization = {firm.id: [] for firm in self._firms()}
        stockout_days = {firm.id: 0 for firm in self._firms()}
        ordered_edges: dict[str, dict[str, int]] = {firm.id: {} for firm in self._firms()}
        shipped_edges: dict[str, dict[str, int]] = {firm.id: {} for firm in self._firms()}
        b2b_received = {firm.id: 0 for firm in self._firms()}
        b2b_shipped = {firm.id: 0 for firm in self._firms()}

        self._draw_market_events(state)
        rival_prices = self._rival_prices(previous)
        for firm in self._firms():
            if not self.env.runtimes[firm.id].active:
                continue
            strategy = self.policies[firm.id].decide_annual(
                firm, previous.get(firm.id), self.config,
                rival_price=rival_prices.get(firm.stage),
            ).validate_for_config(self.config)
            self.strategies[firm.id] = strategy
            self._apply_annual(firm, strategy)
            self.decision_log.annual(year + 1, firm, strategy)
        if self.state_actor is not None:
            self.state_actor.apply_offences(self)
        if self.laws is not None:
            self.laws.apply_yearly(self)
        if self.labor is not None:
            self.labor.year_start(self)
        if self.marketing is not None:
            self.marketing.year_start(self)

        for day in range(self.config.simulation.days_per_year):
            decisions = {}
            for firm in self._firms():
                runtime = self.env.runtimes[firm.id]
                if not runtime.active:
                    continue
                obs = FirmObservation(
                    inventory=runtime.inventory, backlog=runtime.backlog,
                    pipeline_units=sum(runtime.incoming_shipments),
                    on_order=runtime.on_order,
                    recent_demand=self._moving_average(recent_demand[firm.id], 1.0),
                    recent_sales=self._moving_average(recent_sales[firm.id], 0.0),
                    cash=runtime.cash, day_of_year=day,
                    quality_level=runtime.quality_level,
                )
                decisions[firm.id] = self.policies[firm.id].decide_daily(
                    firm, obs, self.strategies[firm.id], self.config
                ).clamped_to(self.strategies[firm.id])
            for firm in self._firms():
                if firm.id not in decisions:
                    continue
                decision = decisions[firm.id]
                self.decision_log.daily(year + 1, day, self.config.simulation.days_per_year, firm.id, decision)
                firm.sell_price = decision.sell_price
                firm.overtime_level = decision.overtime_level
                price_totals[firm.id] += firm.sell_price
                daily_prices[firm.id].append(firm.sell_price)
                band = self.strategies[firm.id]
                self.applied_prices.append((firm.id, firm.sell_price, band.min_price, band.max_price))
            total_demand = self.demand(global_day)
            _, info = self.env.step(total_demand, {key: value.order_qty for key, value in decisions.items()})
            self.region_reporter.daily(self)
            demand_series.append(total_demand)
            factory_order_series.append(sum(
                decisions[f.id].order_qty for f in self.network.firms_in("factory")
                if f.id in decisions
            ))
            global_day += 1
            for firm in self._firms():
                runtime = self.env.runtimes[firm.id]
                series = daily_series[firm.id]
                series["inventory"].append(self.env.inventory_history[firm.id][-1])
                series["backlog"].append(self.env.backlog_history[firm.id][-1])
                series["cash"].append(runtime.cash)
                series["cumulative_profit"].append(runtime.profit)
                if firm.stage == "retailer":
                    series["consumer_units_sold"].append(
                        info["consumer_units_sold"].get(firm.id, 0)
                    )
                    series["demand_share"].append(
                        info["consumer_demand_shares"].get(firm.id, 0)
                    )
                daily_quality[firm.id].append(runtime.quality_level)
                daily_turnover[firm.id].append(runtime.turnover_rate)
                if runtime.backlog > 0:
                    stockout_days[firm.id] += 1
                shipped_total = sum(info["shipments"].get(firm.id, {}).values())
                b2b_received[firm.id] += self.env.orders_received_this_period(firm.id)
                b2b_shipped[firm.id] += shipped_total
                if firm.stage == "retailer":
                    incoming = info["consumer_demand_shares"].get(firm.id, 0)
                    sold = info["consumer_units_sold"].get(firm.id, 0)
                    retailer_served[firm.id] += sold
                    retailer_lost[firm.id] += max(0, incoming - sold)
                    shipped_total += sold
                else:
                    incoming = self.env.orders_received_this_period(firm.id)
                    sold = sum(info["shipments"].get(firm.id, {}).values())
                recent_demand[firm.id] = (recent_demand[firm.id] + [incoming])[-7:]
                recent_sales[firm.id] = (recent_sales[firm.id] + [sold])[-7:]
                capacity = self.env._effective_capacity(firm.id)
                utilization[firm.id].append(min(1.0, shipped_total / capacity) if capacity else 0.0)
                for supplier_id, quantity in info["split_orders"].get(firm.id, {}).items():
                    edge = ordered_edges[firm.id]
                    edge[supplier_id] = edge.get(supplier_id, 0) + quantity
            for supplier_id, allocations in info["shipments"].items():
                for buyer_id, quantity in allocations.items():
                    if buyer_id in shipped_edges:
                        edge = shipped_edges[buyer_id]
                        edge[supplier_id] = edge.get(supplier_id, 0) + quantity
        summaries.append(self._summarize_year(
            starts, history_starts, price_totals, retailer_served, retailer_lost,
            utilization, previous,
        ))
        reports, kpis = self._build_reports(
            year + 1, summaries[-1], price_totals, retailer_served,
            retailer_lost, stockout_days, utilization, daily_turnover,
            daily_quality, ordered_edges, shipped_edges, demand_series,
            factory_order_series,
            b2b_received, b2b_shipped, daily_prices,
        )
        kpis = self._add_experiment_kpis(kpis, reports, annual_reports[-1] if annual_reports else None, summaries[-1])
        kpis = kpis.model_copy(update={
            "market_entries": state.market_entries.get(year + 1, 0),
        })
        self._log_year_events(
            state, year + 1, summaries[-1], previous, utilization, shipped_edges,
        )
        annual_reports.append(reports)
        system_kpis.append(kpis)
        financial_ends = self._financial_snapshot_all()
        for firm in self._firms():
            start = financial_starts[firm.id]
            end = financial_ends[firm.id]
            financial_breakdown[firm.id].append({
                key: end[key] - start[key]
                for key in (
                    "revenue", "purchase_cost", "holding_cost",
                    "backlog_cost", "wage_cost", "hiring_cost",
                    "rnd_cost", "handling_cost", "fixed_cost", "interest_cost", "negative_interest_cost", "investment_depreciation", "profit",
                )
            } | {"cash": end["cash"]})
        # P4b fix: exits are deterministic year-end events; cash freezes
        # from the following tick after the configured grace period.
        exits_before = len(self.exits)
        for firm in self._firms():
            runtime = self.env.runtimes[firm.id]
            if not runtime.active:
                continue
            summary = summaries[-1][firm.id]
            runtime.last_year_revenue = summary.revenue
            runtime.consecutive_loss_years = runtime.consecutive_loss_years + 1 if summary.profit < 0 else 0
            bank = self.config.bank
            if bank.enabled:
                runtime.credit_limit = max(bank.credit_limit_min,
                    bank.credit_limit_revenue_fraction * summary.revenue
                    + bank.credit_limit_initial_cash_fraction * runtime.initial_cash)
            reports[firm.id] = reports[firm.id].model_copy(update={
                "interest_cost": financial_breakdown[firm.id][-1]["interest_cost"],
            })
        if self.env.brand_book is not None:
            self._last_brand_units = dict(self.env.brand_book.brand_units)
            brand_rows, class_rows = self.env.brand_book.year_end(self.env, self.network, year + 1)
            state.brand_reports.extend(brand_rows)
            state.class_reports.extend(class_rows)
        self.decision_log.finish_year()
        self.region_reporter.finish_year(self, year + 1, summaries[-1])
        self._apply_bankruptcy(year + 1, state.events)
        system_kpis[-1] = system_kpis[-1].model_copy(update={
            "bankruptcies": len(self.exits) - exits_before,
        })
        state.global_day = global_day
        state.year = year + 1
        self._enter_market(state)
        changes = self._change_strategies(state)
        self.long_run.year_end(self, state)
        geo = self.env.geography
        if geo is not None:
            geo.year_end(self, state)
        if self.state_actor is not None:
            self.state_actor.year_end(self, state)
            self.state_actor.takeovers(self, state)
        if self.lab is not None:
            self.lab.year_end(self, state)
        if self.marketing is not None:
            self.marketing.year_end(self, state)
        if self.holdings is not None:
            self.holdings.year_end(self, state)
        if self.laws is not None:
            self.laws.year_end(self, state)
        for event in state.events[event_start:]:
            if event["event"] in ("expand_started", "site_started", "rnd_started", "strategy_change", "transport_switch"):
                self.decision_log.record(event["year"], event["firm"], event["event"], event["details"], event["details"])
        update = {"market_entries": state.market_entries.get(state.year, 0), "strategy_changes": changes,
                  "price_index": self.long_run.price_index, "population_index": self.long_run.population_index,
                  "trend": self.long_run.trend, "fx_rate": self.env.fx_rate,
                  **self._geography_kpis(), **self._state_kpis(), **self._research_kpis(),
                  **self._phase10_kpis(),
                  **self._category_kpis(),
                  "total_profit": sum(s.profit for s in summaries[-1].values())}
        for stage in STAGES:
            firms = self.network.firms_in(stage)
            update[f"negative_interest_{stage}"] = sum(financial_breakdown[f.id][-1]["negative_interest_cost"] for f in firms)
            update[f"interest_cost_{stage}"] = sum(financial_breakdown[f.id][-1]["interest_cost"] for f in firms)
            update[f"debt_{stage}"] = sum(max(0.0, -self.env.runtimes[f.id].cash) for f in firms
                                         if self.env.runtimes[f.id].active)
            update[f"active_firms_{stage}"] = sum(self.env.runtimes[f.id].active for f in firms)
        system_kpis[-1] = system_kpis[-1].model_copy(update=update)

    def _phase10_kpis(self) -> dict[str, float]:
        out: dict[str, float] = {}
        book = self.env.brand_book
        revenue = sum(book.channel_revenue.values())
        out["restaurant_revenue_share"] = book.channel_revenue["restaurant"] / revenue if revenue else 0.0
        out["restaurant_unit_share"] = (book.channel_units["restaurant"] / sum(book.channel_units.values())
                                        if sum(book.channel_units.values()) else 0.0)
        book.channel_units = {"store": 0, "restaurant": 0}
        book.channel_revenue = {"store": 0.0, "restaurant": 0.0}
        out["active_restaurants"] = sum(1 for f in self.network.firms_in("retailer")
                                        if f.channel == "restaurant" and self.env.runtimes[f.id].active)
        if self.marketing is not None:
            out["marketing_spend"] = self.marketing.stats["marketing_spend"]
            self.marketing.stats = {"marketing_spend": 0.0}
        if self.holdings is not None:
            out.update(self.holdings.stats)
            out["stakes_held"] = len(self.holdings.stakes)
            self.holdings.stats = {"dividends": 0.0, "stakes_bought": 0, "stakes_sold": 0}
        if self.laws is not None:
            out["laws_enacted"] = len(self.laws.enacted)
        if self.labor is not None:
            out.update(self.labor.stats)
            self.labor.stats = {"open_positions": 0, "poached_workers": 0, "hires": 0}
            index = self.labor.wage_index
            out["wage_index_mean"] = sum(index.values()) / len(index) if index else 1.0
            regions = list(self.labor.pool)
            out["labor_tightness"] = (sum(self.labor.tightness(self, r) for r in regions) / len(regions)) if regions else 0.0
        return out

    def _research_kpis(self) -> dict[str, float]:
        lab = self.lab
        if lab is None:
            return {}
        stats = dict(lab.stats)
        lab.stats = {key: type(value)() for key, value in lab.stats.items()}
        return {**stats, "rnd_running": len(lab.running)}

    def _state_kpis(self) -> dict[str, float]:
        actor = self.state_actor
        if actor is None:
            return {}
        stats = dict(actor.stats)
        actor.stats = actor._empty_stats()
        return {**stats, "fear": max(actor.fear.values(), default=0.0)}

    def close_firm_now(self, firm_id: str, year: int, state: RunState, event: str, details: str) -> None:
        """Phase 6: close a firm at once (poisoning, takeover), ignoring the stage minimum."""
        runtime = self.env.runtimes[firm_id]
        if not runtime.active:
            return
        runtime.active = False
        self.env.close_firm(firm_id)
        self.exits[firm_id] = year
        state.events.append({"year": year, "day": self.config.simulation.days_per_year,
                             "firm": firm_id, "event": event, "details": details})

    def spin_off(self, parent: Firm, state: RunState, region: str, capacity: int, machines: int, staff: int) -> str:
        """Phase 6: a site sold off by antitrust order becomes a new firm."""
        self._spin_offs = getattr(self, "_spin_offs", 0) + 1
        firm = parent.model_copy(deep=True, update={
            "id": f"{parent.stage}_s{self._spin_offs:02d}", "name": f"{parent.name} ({REGION_DE.get(region, region)})",
            "region": region, "extra_regions": [], "capacity": capacity, "machine_capacity": machines,
            "employees": staff, "inventory": 0, "backlog": 0, "suppliers": [],
            "cash": parent.cash * self.config.market_entry.start_cash_fraction,
        })
        self.add_firm(firm, state)
        state.events[-1].update(event="spin_off", details=f"abgespalten von {parent.id}")
        return firm.id

    def _geography_kpis(self) -> dict[str, float]:
        geo = self.env.geography
        if geo is None:
            return {}
        stats = dict(geo.stats)
        geo.stats = {key: type(value)() for key, value in geo.stats.items()}
        active = [f for f in self._firms() if self.env.runtimes[f.id].active and f.stage != "retailer"]
        return {**stats, "firms_using_service": sum(f.transport_mode == "service" for f in active),
                "fuel_index": geo.fuel_index}

    def _category_kpis(self) -> dict[str, float]:
        """Export volume and consumer shares per category of the finished year."""
        book = self.env.brand_book
        if book is None or not book.categories_on:
            return {}
        units = getattr(self, "_last_brand_units", {})
        total = sum(units.values()) or 1
        shares = {c: 0.0 for c in book.base_share}
        for brand_id, sold in units.items():
            shares[book.brands[brand_id].category] = shares.get(book.brands[brand_id].category, 0.0) + sold / total
        exported = book.export_units
        book.export_units = 0
        return {"export_units": exported, **{f"share_{c}": v for c, v in shares.items() if c in ("beer", "wine", "spirits")}}

    def _enter_market(self, state: RunState) -> None:
        """Draw exactly three numbers per stage, including disabled/full stages."""
        cfg = self.config.market_entry
        archetypes = sorted(FirmPolicy._PRESETS)
        for stage in STAGES:
            roll, archetype_roll, reputation_roll = [self._phase1_rng.random() for _ in range(3)]
            active = [f for f in self.network.firms_in(stage) if self.env.runtimes[f.id].active]
            if not cfg.enabled or not active:
                continue
            revenue = sum(state.summaries[-1][f.id].revenue for f in active)
            margin = sum(state.summaries[-1][f.id].profit for f in active) / revenue if revenue else 0.0
            probability = min(cfg.max_probability, cfg.base_probability
                              + cfg.margin_slope * max(0.0, margin - cfg.margin_threshold))
            capacity_share = cfg.start_capacity_fraction
            stage_capacity = sum(self.env._effective_capacity(f.id) for f in active if f.channel != "restaurant")
            needed = self.demand.mean
            if stage == "retailer" and self.config.restaurants.enabled:
                # Stores serve the demand at home; restaurant seats do not count for it.
                needed *= 1 - self.config.restaurants.out_of_home_share
            if cfg.shortage_capacity_ratio and stage_capacity < cfg.shortage_capacity_ratio * needed:
                # A starved stage attracts a full-size newcomer.
                probability, capacity_share = 1.0, 1.0
            book = self.env.brand_book
            if stage == "factory" and cfg.shortage_capacity_ratio and book.categories_on:
                # Producers are checked per category: plenty of wine does not replace missing beer.
                for c, share_c in book.base_share.items():
                    cap_c = sum(self.env._effective_capacity(f.id) for f in active if f.category == c)
                    if cap_c < cfg.shortage_capacity_ratio * self.demand.mean * share_c:
                        probability, capacity_share = 1.0, 1.0
            want_restaurant = False
            if stage == "retailer" and self.config.restaurants.enabled:
                # Phase 10: too few seats for the out-of-home demand bring a new restaurant.
                seats = sum(self.env._effective_capacity(f.id) for f in active if f.channel == "restaurant")
                guests = self.demand.mean * self.config.restaurants.out_of_home_share
                stores_short = cfg.shortage_capacity_ratio and stage_capacity < cfg.shortage_capacity_ratio * needed
                if seats < max(1.0, cfg.shortage_capacity_ratio) * guests and not stores_short:
                    probability, capacity_share, want_restaurant = 1.0, 1.0, True
            if stage == "factory" and book is not None and book.categories_on:
                # A category without any producer gets a new one at once.
                present = {f.category for f in active}
                if any(c not in present for c in book.base_share):
                    probability = 1.0
            if roll >= probability or len(active) >= cfg.max_firms_per_stage[stage]:
                continue
            pool = active
            if stage == "retailer":
                restaurants = [f for f in active if f.channel == "restaurant"]
                if want_restaurant:
                    pool = restaurants or self._restaurant_templates or active
                else:
                    pool = [f for f in active if f.channel != "restaurant"] or self._store_templates or active
            book = self.env.brand_book
            if stage == "factory" and book is not None and book.categories_on:
                # Phase 6: a new producer enters the category with the least capacity per demand.
                supply = {c: 0.0 for c in book.base_share}
                for f in active:
                    if f.category in supply:
                        supply[f.category] += self.env._effective_capacity(f.id)
                category = min(sorted(supply), key=lambda c: supply[c] / book.base_share[c])
                pool = [f for f in active if f.category == category] or active
            template = sorted(pool, key=lambda f: (self.env.runtimes[f.id].cash, f.id))[len(pool) // 2]
            if stage == "factory" and book is not None and book.categories_on and template.category != category:
                template = template.model_copy(update={"category": category, "importer": False})
            self._entry_counters[stage] += 1
            counter = self._entry_counters[stage]
            name_key = ("factory_import" if template.importer else f"factory_{template.category}") if stage == "factory" else (
                "restaurant" if template.channel == "restaurant" else stage)
            names = cfg.names.get(name_key, cfg.names[stage])
            cycle, index = divmod(counter - 1, len(names))
            name = names[index] + (f" {cycle + 1}" if cycle else "")
            firm = template.model_copy(deep=True, update={
                "id": f"{stage}_e{counter:02d}", "name": name,
                "archetype": archetypes[int(archetype_roll * len(archetypes))],
                "cash": cfg.start_cash_fraction * self._entry_cash[stage],
                "capacity": max(1, round(template.capacity * capacity_share)),
                "machine_capacity": max(1, round(template.machine_capacity * capacity_share))
                    if template.machine_capacity else 0,
                "employees": max(1, round(template.employees * capacity_share)),
                "reputation": cfg.start_reputation[0] + reputation_roll * (cfg.start_reputation[1] - cfg.start_reputation[0]),
                "quality_level": template.quality_level * cfg.start_quality_fraction,
                "inventory": 0, "backlog": 0, "suppliers": [],
                "region": self.env.geography.entrant_region(self, stage) if self.env.geography else template.region,
                "extra_regions": [], "transport_mode": "own",
            })
            self.add_firm(firm, state)
            # add_firm also supports external registration before the next year.
            state.market_entries[state.year + 1] -= 1
            state.market_entries[state.year] = state.market_entries.get(state.year, 0) + 1
            state.events[-1].update(year=state.year, day=self.config.simulation.days_per_year,
                                    details=f"Strategie {ARCHETYPE_DE.get(firm.archetype, firm.archetype)}")

    def _change_strategies(self, state: RunState) -> int:
        """Use a simultaneous ranking and two unconditional draws per firm."""
        cfg = self.config.strategy_change
        bottom = set()
        rankings = {}
        mean_returns: dict[str, dict[str, float]] = {}
        for stage in STAGES:
            active = [f for f in self.network.firms_in(stage)
                      if self.env.runtimes[f.id].active and state.annual_reports[-1][f.id].archetype]
            ordered = sorted(active, key=lambda f: (
                state.summaries[-1][f.id].profit / max(1.0, state.summaries[-1][f.id].revenue), f.id))
            bottom.update(f.id for f in ordered[:len(ordered) // 3])
            returns: dict[str, list[float]] = {}
            for reports in state.annual_reports[-cfg.imitation_window_years:]:
                for f in active:
                    report = reports[f.id]
                    if report.archetype and report.revenue > 0:
                        returns.setdefault(report.archetype, []).append(report.profit / report.revenue)
            rankings[stage] = sorted(returns, key=lambda a: (-sum(returns[a]) / len(returns[a]), a))
            mean_returns[stage] = {a: sum(v) / len(v) for a, v in returns.items()}
        changes = 0
        for firm in self._firms():
            roll, choice_roll = self._phase1_rng.random(), self._phase1_rng.random()
            runtime = self.env.runtimes[firm.id]
            if (not cfg.enabled or not runtime.active or firm.stage not in cfg.stages
                    or not state.annual_reports[-1][firm.id].archetype):
                continue
            summary = state.summaries[-1][firm.id]
            bad = summary.profit < 0 or (cfg.count_bottom_third and firm.id in bottom)
            runtime.consecutive_bad_years = runtime.consecutive_bad_years + 1 if bad else 0
            if runtime.consecutive_bad_years < cfg.bad_years_trigger or (
                runtime.last_strategy_change_year is not None
                and state.year - runtime.last_strategy_change_year < cfg.lockout_years
            ):
                continue
            old = firm.archetype
            reason = "explore" if roll < cfg.explore_probability else "imitate"
            options = sorted(a for a in FirmPolicy._PRESETS if a != old) if reason == "explore" else [
                a for a in rankings[firm.stage] if a != old]
            if reason == "imitate" and options:
                returns = mean_returns[firm.stage]
                own = returns.get(old, float("-inf"))
                if returns[options[0]] - own < cfg.min_return_gap:
                    options = []
            if not options:
                continue
            new = options[int(choice_roll * len(options))] if reason == "explore" else options[0]
            firm.archetype = new
            cost = cfg.switch_cost_fraction_of_revenue * summary.revenue
            runtime.fixed_cost += cost
            runtime.cash -= cost
            firm.reputation = self._clamp(firm.reputation - cfg.reputation_dip)
            runtime.consecutive_bad_years = 0
            runtime.last_strategy_change_year = state.year
            state.summaries[-1][firm.id] = replace(summary, profit=summary.profit - cost, cash=runtime.cash)
            report = state.annual_reports[-1][firm.id]
            state.annual_reports[-1][firm.id] = report.model_copy(update={
                "profit": report.profit - cost, "reputation": firm.reputation,
            })
            financial = state.financial_breakdown[firm.id][-1]
            financial["fixed_cost"] += cost
            financial["profit"] -= cost
            financial["cash"] = runtime.cash
            state.events.append({"year": state.year, "day": self.config.simulation.days_per_year,
                                 "firm": firm.id, "event": "strategy_change",
                                 "details": f"{ARCHETYPE_DE.get(old, old)} → {ARCHETYPE_DE.get(new, new)}, "
                                            f"{'ausprobiert' if reason == 'explore' else 'nachgeahmt'}"})
            changes += 1
        return changes

    def _build_reports(
        self, year, summaries, prices, served, lost, stockouts, utilization,
        turnover, qualities, ordered_edges, shipped_edges, demand_series,
        factory_order_series,
        b2b_received, b2b_shipped,
        daily_prices,
    ):
        days = self.config.simulation.days_per_year
        total_sales = sum(served.values())
        retailer_shares = {
            firm.id: (served[firm.id] / total_sales if total_sales else 0.0)
            for firm in self.network.firms_in("retailer")
        }
        stage_revenue = {stage: sum(summaries[f.id].revenue for f in self.network.firms_in(stage)
                                    if self.env.runtimes[f.id].active) for stage in STAGES}
        category_revenue = {f.category: sum(summaries[p.id].revenue for p in self.network.firms_in("factory")
                                          if p.category == f.category and self.env.runtimes[p.id].active)
                            for f in self.network.firms_in("factory")}
        reports = {}
        for firm in self._firms():
            summary = summaries[firm.id]
            average_quality = sum(qualities[firm.id]) / len(qualities[firm.id])
            supplier_reliability = {
                supplier: min(1.0, shipped_edges[firm.id].get(supplier, 0) / quantity)
                for supplier, quantity in ordered_edges[firm.id].items() if quantity > 0
            }
            fill = (
                service_level(served[firm.id], served[firm.id] + lost[firm.id])
                if firm.stage == "retailer"
                else service_level(b2b_shipped[firm.id], b2b_received[firm.id])
            )
            problems = []
            capacity_utilization = sum(utilization[firm.id]) / len(utilization[firm.id])
            self._apply_feedback_links(
                firm, fill, capacity_utilization, daily_prices[firm.id]
            )
            if stockouts[firm.id] > 0.15 * days:
                problems.append("Too many stockouts")
            if capacity_utilization > 0.9:
                problems.append("Capacity near limit")
            competitors = [f for f in self.network.firms_in(firm.stage) if f.id != firm.id]
            if competitors and average_quality < max(self.env.runtimes[f.id].quality_level for f in competitors) - 0.1:
                problems.append("Quality below premium competitors")
            if self.env.runtimes[firm.id].cash < 0:
                problems.append("Negative cash")
            if summary.profit < 0:
                problems.append("Losing money")
            reports[firm.id] = AnnualReport(
                archetype=firm.archetype,
                year=year, firm_id=firm.id, revenue=summary.revenue,
                profit=summary.profit,
                market_share=(retailer_shares.get(firm.id, 0.0) if firm.stage == "retailer" else
                              summary.revenue / stage_revenue[firm.stage]
                              if stage_revenue[firm.stage] and self.env.runtimes[firm.id].active else 0.0),
                category_share=(summary.revenue / category_revenue[firm.category]
                                if firm.stage == "factory" and category_revenue[firm.category]
                                and self.env.runtimes[firm.id].active else 0.0),
                service_level=fill,
                average_sell_price=(
                    prices[firm.id] / len(daily_prices[firm.id])
                    if daily_prices[firm.id] else firm.sell_price
                ),
                average_quality=average_quality, stockout_days=stockouts[firm.id],
                lost_sales=lost[firm.id],
                employee_turnover=(sum(turnover[firm.id]) / len(turnover[firm.id])) * 365,
                average_wage=firm.wage_level, reputation=firm.reputation,
                capacity_utilization=capacity_utilization,
                supplier_reliability=supplier_reliability, main_problems=problems,
            )
        total_demand = int(sum(demand_series))
        total_served = sum(served.values())
        customer_revenue = sum(
            summaries[firm.id].revenue for firm in self.network.firms_in("retailer")
        )
        kpis = SystemKPIs(
            year=year, total_profit=sum(item.profit for item in summaries.values()),
            total_backlog=sum(runtime.backlog for runtime in self.env.runtimes.values()),
            total_lost_sales=sum(lost.values()),
            average_customer_price=customer_revenue / total_served if total_served else 0.0,
            average_quality=sum(report.average_quality for report in reports.values()) / len(reports),
            market_concentration=herfindahl_index(list(retailer_shares.values())),
            bullwhip_ratio=bullwhip_variance_ratio(factory_order_series, demand_series),
            service_level=service_level(total_served, total_demand),
        )
        kpis = kpis.model_copy(update={f"hhi_{stage}": herfindahl_index(
            [reports[f.id].market_share for f in self.network.firms_in(stage)])
            for stage in STAGES if stage != "retailer"})
        return reports, kpis

    def _apply_feedback_links(
        self, firm: Firm, fill: float, capacity_utilization: float,
        daily_prices: list[float],
    ) -> None:
        """Apply deterministic year-end feedback links in their required order."""
        runtime = self.env.runtimes[firm.id]

        # Feedback-link 4: overload reduces current quality before reputation uses it.
        capacity_cfg = self.config.capacity
        overload = max(
            0.0, capacity_utilization - capacity_cfg.overload_utilization_threshold
        )
        quality_penalty = capacity_cfg.overload_quality_penalty * overload
        runtime.quality_level = self._clamp(runtime.quality_level - quality_penalty)
        firm.quality_level = self._clamp(firm.quality_level - quality_penalty)
        quality = firm.quality_level

        # Feedback-links 1 and 3: wages build employer brand; volatile prices erode trust.
        reputation_cfg = self.config.reputation
        wage_reference = self.config.workforce.wage_reference
        wage_factor = self._clamp(
            0.5 + 0.5 * (firm.wage_level - wage_reference) / wage_reference
        )
        target = (
            reputation_cfg.service_weight * fill
            + reputation_cfg.quality_weight * quality
            + reputation_cfg.wage_weight * wage_factor
        )
        mean_price = sum(daily_prices) / len(daily_prices) if daily_prices else 0.0
        price_cv = (
            pstdev(daily_prices) / mean_price
            if len(daily_prices) >= 2 and mean_price != 0 else 0.0
        )
        volatility_factor = self._clamp(
            1.0 - reputation_cfg.price_volatility_penalty * price_cv,
            reputation_cfg.price_volatility_floor, 1.0,
        )
        target = self._clamp(target * volatility_factor)
        firm.reputation = self._clamp(
            firm.reputation
            + reputation_cfg.reputation_adjust_speed * (target - firm.reputation)
        )

        # Feedback-link 2: annual realized fill becomes earned reliability.
        reliability_speed = self.config.reliability.reliability_adjust_speed
        firm.reliability = self._clamp(
            firm.reliability + reliability_speed * (fill - firm.reliability)
        )

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _firms(self) -> list[Firm]:
        return sorted(
            (firm for stage in STAGES for firm in self.network.firms_in(stage)),
            key=lambda firm: firm.id,
        )

    def _apply_annual(self, firm: Firm, strategy: AnnualStrategy) -> None:
        firm.wage_level = strategy.wage_level
        firm.r_and_d_budget = strategy.r_and_d_budget
        firm.overtime_level = strategy.overtime_level
        firm.supplier_priority = strategy.supplier_priority
        if self.labor is None:
            firm.employees = max(self.config.workforce.min_employees, firm.employees + strategy.hiring_plan)
        # With a labour market, hiring happens in LaborMarket.year_start, best payers first.
        runtime = self.env.runtimes[firm.id]
        runtime.wage_level = firm.wage_level
        runtime.employees = firm.employees

    def _apply_bankruptcy(
        self, completed_years: int, events: list[dict[str, object]] | None = None,
    ) -> None:
        """P4b fix: close insolvent firms at year-end after the grace period."""
        cfg = self.config.bankruptcy
        if not cfg.enabled or completed_years < cfg.min_years_before_exit:
            return
        candidates = []
        for firm_id, runtime in self.env.runtimes.items():
            if not runtime.active:
                continue
            runtime.negative_cash_years = runtime.negative_cash_years + 1 if runtime.cash < 0 else 0
            insolvent = (
                (cfg.cash_floor_fraction is not None
                 and runtime.cash < -cfg.cash_floor_fraction * runtime.initial_cash)
                or (cfg.negative_cash_years > 0
                    and runtime.negative_cash_years >= cfg.negative_cash_years)
                or (cfg.cash_threshold is not None and runtime.cash < cfg.cash_threshold)
            )
            if self.config.bank.enabled:
                insolvent = runtime.cash < -runtime.credit_limit
            if insolvent:
                candidates.append((runtime.cash, firm_id))
        # The weakest firm leaves first; a stage keeps its minimum number of firms.
        exits_per_stage: dict[str, int] = {}
        for _, firm_id in sorted(candidates):
            stage = self.network.firm(firm_id).stage
            active = sum(self.env.runtimes[f.id].active for f in self.network.firms_in(stage))
            firm = self.network.firm(firm_id)
            same_category = sum(self.env.runtimes[f.id].active for f in self.network.firms_in(stage)
                                if f.category == firm.category and not f.importer)
            # Phase 6: the last domestic producer of a category is protected like a stage minimum.
            protected = (stage == "factory" and not firm.importer and same_category <= 1
                         and cfg.min_firms_per_stage > 0)
            if active <= cfg.min_firms_per_stage or protected:
                bank = self.config.bank
                runtime = self.env.runtimes[firm_id]
                if bank.enabled and bank.restructuring and runtime.cash < 0:
                    written_off = -runtime.cash
                    runtime.adjust_cash(written_off)
                    runtime.consecutive_loss_years = 0
                    firm = self.network.firm(firm_id)
                    firm.reputation = self._clamp(firm.reputation - bank.restructuring_reputation_hit)
                    if events is not None:
                        events.append({
                            "year": completed_years, "day": self.config.simulation.days_per_year,
                            "firm": firm_id, "event": "restructuring",
                            "details": f"Bank schreibt {chf(written_off)} ab",
                        })
                continue
            if cfg.max_exits_per_stage_per_year and exits_per_stage.get(stage, 0) >= cfg.max_exits_per_stage_per_year:
                continue
            exits_per_stage[stage] = exits_per_stage.get(stage, 0) + 1
            self.env.runtimes[firm_id].active = False
            self.env.close_firm(firm_id)
            self.exits[firm_id] = completed_years
            if events is not None:
                events.append({
                    "year": completed_years, "day": self.config.simulation.days_per_year,
                    "firm": firm_id, "event": "bankruptcy",
                    "details": (f"Bank kündigt Kredit, Cash {chf(self.env.runtimes[firm_id].cash)}, "
                                f"Limite {chf(self.env.runtimes[firm_id].credit_limit)}"
                                if self.config.bank.enabled else f"Cash {chf(self.env.runtimes[firm_id].cash)}"),
                })

    def _add_experiment_kpis(self, kpis, reports, previous_reports, summaries):
        update: dict[str, float | int] = {}
        for stage in STAGES:
            active = [f for f in self.network.firms_in(stage) if self.env.runtimes[f.id].active]
            revenue = sum(summaries[f.id].revenue for f in active)
            update[f"margin_{stage}"] = (
                sum(summaries[f.id].profit for f in active) / revenue if revenue else 0.0
            )
            update[f"utilization_{stage}"] = (
                sum(reports[f.id].capacity_utilization for f in active) / len(active)
                if active else 0.0
            )
        retailers = self.network.firms_in("retailer")
        if previous_reports is not None:
            update["market_share_movement"] = sum(
                abs(reports[f.id].market_share - previous_reports[f.id].market_share)
                for f in retailers
            )
        update["firms_with_loss"] = sum(
            summaries[f.id].profit < 0 for f in self._firms() if self.env.runtimes[f.id].active
        )
        prices = [
            reports[f.id].average_sell_price for f in retailers if self.env.runtimes[f.id].active
        ]
        update["retailer_price_spread"] = pstdev(prices) if len(prices) >= 2 else 0.0
        return kpis.model_copy(update=update)

    def _log_year_events(self, state, year, summaries, previous, utilization, shipped_edges) -> None:
        """Price moves above 5 %, supplier switches and capacity ceilings."""
        days = self.config.simulation.days_per_year
        for firm in self._firms():
            runtime = self.env.runtimes[firm.id]
            if not runtime.active:
                continue
            old = previous.get(firm.id)
            new_price = summaries[firm.id].avg_sell_price
            if old is not None and old.avg_sell_price > 0:
                change = new_price / old.avg_sell_price - 1
                if abs(change) > 0.05:
                    state.events.append({
                        "year": year, "day": 1, "firm": firm.id,
                        "event": "price_increase" if change > 0 else "price_cut",
                        "details": f"Durchschnittspreis {old.avg_sell_price:.2f} → {new_price:.2f} ({change:+.1%})",
                    })
            shipped = shipped_edges[firm.id]
            if shipped:
                top = max(sorted(shipped), key=lambda supplier: shipped[supplier])
                before = state.main_supplier.get(firm.id)
                if before is not None and before != top:
                    state.events.append({
                        "year": year, "day": days, "firm": firm.id, "event": "supplier_switch",
                        "details": f"grösster Lieferant {before} → {top}",
                    })
                state.main_supplier[firm.id] = top
            episodes: list[list[int]] = []
            for index, value in enumerate(utilization[firm.id]):
                if value <= 0.95:
                    continue
                # Only a pause of at least 30 days below 95 % starts a new episode.
                if episodes and index - episodes[-1][1] - 1 < 30:
                    episodes[-1][1] = index
                else:
                    episodes.append([index, index])
            for start, end in episodes:
                if end - start + 1 >= 7:
                    state.events.append({
                        "year": year, "day": start + 1, "firm": firm.id,
                        "event": "capacity_limit",
                        "details": f"über 95 % ausgelastet während {end - start + 1} Tagen",
                    })

    def _rival_prices(self, previous: dict[str, YearSummary]) -> dict[str, float]:
        """Average last-year selling price of the still active firms per stage."""
        prices: dict[str, float] = {}
        for stage in STAGES:
            values = [
                previous[firm.id].avg_sell_price for firm in self.network.firms_in(stage)
                if firm.id in previous and self.env.runtimes[firm.id].active
            ]
            if values:
                prices[stage] = sum(values) / len(values)
        return prices

    def _financial_starts(self) -> dict[str, tuple[float, float]]:
        return {key: (runtime.revenue, runtime.profit) for key, runtime in self.env.runtimes.items()}

    def _financial_snapshot_all(self) -> dict[str, dict[str, float]]:
        """Return cumulative accounting counters using dashboard field names."""
        return {
            firm_id: {
                "revenue": float(getattr(runtime, "revenue", 0.0)),
                "purchase_cost": float(getattr(runtime, "purchase_cost", 0.0)),
                "holding_cost": float(getattr(runtime, "cumulative_holding_cost", 0.0)),
                "backlog_cost": float(getattr(runtime, "cumulative_backlog_cost", 0.0)),
                "wage_cost": float(getattr(runtime, "wage_cost", 0.0)),
                "hiring_cost": float(getattr(runtime, "hiring_cost", 0.0)),
                "rnd_cost": float(getattr(runtime, "rnd_spend", 0.0)),
                "handling_cost": float(getattr(runtime, "handling_cost", 0.0)),
                "fixed_cost": float(getattr(runtime, "fixed_cost", 0.0)),
                "investment_depreciation": getattr(runtime, "investment_depreciation", 0.0),
                "interest_cost": runtime.interest_cost,
                "negative_interest_cost": runtime.negative_interest_cost,
                "profit": float(getattr(runtime, "profit", 0.0)),
                "cash": float(getattr(runtime, "cash", 0.0)),
            }
            for firm_id, runtime in self.env.runtimes.items()
        }

    def _summarize_year(self, starts, history_starts, prices, served, lost, utilization, previous):
        days = self.config.simulation.days_per_year
        result = {}
        stage_revenue = {
            stage: sum(self.env.runtimes[f.id].revenue - starts[f.id][0]
                       for f in self.network.firms_in(stage))
            for stage in STAGES
        }
        for firm in self._firms():
            runtime = self.env.runtimes[firm.id]
            inv_start, back_start = history_starts[firm.id]
            inv = self.env.inventory_history[firm.id][inv_start:]
            back = self.env.backlog_history[firm.id][back_start:]
            revenue_start, profit_start = starts[firm.id]
            denominator = served[firm.id] + lost[firm.id]
            revenue = runtime.revenue - revenue_start
            share = revenue / stage_revenue[firm.stage] if stage_revenue[firm.stage] else 0.0
            old_share = previous[firm.id].market_share if firm.id in previous else share
            result[firm.id] = YearSummary(
                revenue=revenue,
                profit=runtime.profit - profit_start,
                avg_inventory=sum(inv) / len(inv) if inv else 0.0,
                avg_backlog=sum(back) / len(back) if back else 0.0,
                lost_sales=lost[firm.id],
                service_level=served[firm.id] / denominator if denominator else 1.0,
                avg_sell_price=prices[firm.id] / days,
                quality=runtime.quality_level,
                capacity_utilization=(
                    sum(utilization[firm.id]) / len(utilization[firm.id])
                    if utilization[firm.id] else 0.0
                ),
                cash=runtime.cash,
                market_share=share, market_share_change=share - old_share,
            )
        return result

    @staticmethod
    def _moving_average(values: list[int], default: float) -> float:
        return sum(values) / len(values) if values else default
