"""S8 two-level simulation runner for the full market mode."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from statistics import pstdev
from typing import Callable

from market_sim.config import MarketConfig
from market_sim.environment import MarketEnvironment, MarketResult
from market_sim.kpi import (
    AnnualReport, SystemKPIs, bullwhip_variance_ratio, herfindahl_index,
    service_level,
)
from market_sim.models import STAGES, Firm, SupplyNetwork
from market_sim.policies import FirmPolicy
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


class ConsumerDemandGenerator:
    """P4b fix: seeded demand with price elasticity and annual seasonality."""

    def __init__(
        self, mean: int, seed: int, *, days_per_year: int = 365,
        price_elasticity: float = 0.0, reference_price: float = 4.99,
        min_mult: float = 0.3, max_mult: float = 2.0,
        seasonal_amplitude: float = 0.0, seasonal_phase_days: float = 90.0,
    ) -> None:
        self.mean = max(0, int(mean))
        self.days_per_year = max(1, int(days_per_year))
        self.price_elasticity = max(0.0, price_elasticity)
        self.reference_price = reference_price
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.seasonal_amplitude = seasonal_amplitude
        self.seasonal_phase_days = seasonal_phase_days
        self._rng = random.Random(seed)

    def seasonal_factor(self, global_day: int) -> float:
        factor = 1 + self.seasonal_amplitude * math.sin(
            2 * math.pi * ((global_day % self.days_per_year) - self.seasonal_phase_days)
            / self.days_per_year
        )
        return max(float.fromhex("0x1.0p-1022"), factor)

    def elasticity_multiplier(self, avg_active_retail_price: float | None) -> float:
        if avg_active_retail_price is None or avg_active_retail_price <= 0:
            return 1.0
        raw = (self.reference_price / avg_active_retail_price) ** self.price_elasticity
        return max(self.min_mult, min(self.max_mult, raw))

    def __call__(self, global_day: int, avg_active_retail_price: float | None = None) -> int:
        noise = self._rng.uniform(0.9, 1.1)
        effective = (
            self.mean * self.seasonal_factor(global_day)
            * self.elasticity_multiplier(avg_active_retail_price) * noise
        )
        return max(0, round(effective))


class SimulationRunner:
    def __init__(
        self, network: SupplyNetwork, config: MarketConfig,
        policies: dict[str, FirmPolicy], seed: int,
    ) -> None:
        self.network = network
        self.config = config
        self.policies = policies
        firm_ids = {firm.id for firm in self._firms()}
        if set(policies) != firm_ids:
            raise ValueError("policies must contain exactly one policy per firm")
        demand = config.demand
        self.demand = ConsumerDemandGenerator(
            demand.daily_demand_units, seed,
            days_per_year=config.simulation.days_per_year,
            price_elasticity=demand.price_elasticity,
            reference_price=demand.reference_price,
            min_mult=demand.elasticity_min_mult,
            max_mult=demand.elasticity_max_mult,
            seasonal_amplitude=demand.seasonal_amplitude,
            seasonal_phase_days=demand.seasonal_phase_days,
        )
        self.env = MarketEnvironment(
            network, config=config,
            horizon=config.simulation.days_per_year * config.simulation.years,
            consumer_demand_mode="attractiveness_lost",
            enforce_capacity=True, enable_workforce=True, enable_rnd=True,
        )
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
        return RunResult(
            years=state.year, network=self.network, yearly_summaries=state.summaries,
            final_result=self.env.get_result(), annual_reports=state.annual_reports,
            system_kpis=state.system_kpis,
            daily_series=state.daily_series, days_total=state.global_day,
            financial_breakdown=state.financial_breakdown,
            exits=dict(self.exits),
        )

    def run_year(self, state: RunState) -> None:
        """Simulate one full year and append its reports to ``state``."""
        year = state.year
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

        for firm in self._firms():
            if not self.env.runtimes[firm.id].active:
                continue
            strategy = self.policies[firm.id].decide_annual(
                firm, previous.get(firm.id), self.config
            ).validate_for_config(self.config)
            self.strategies[firm.id] = strategy
            self._apply_annual(firm, strategy)

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
                firm.sell_price = decision.sell_price
                firm.overtime_level = decision.overtime_level
                price_totals[firm.id] += firm.sell_price
                daily_prices[firm.id].append(firm.sell_price)
                band = self.strategies[firm.id]
                self.applied_prices.append((firm.id, firm.sell_price, band.min_price, band.max_price))
            active_retail_prices = [
                firm.sell_price for firm in self.network.firms_in("retailer")
                if self.env.runtimes[firm.id].active
            ]
            average_price = (
                sum(active_retail_prices) / len(active_retail_prices)
                if active_retail_prices else None
            )
            total_demand = self.demand(global_day, average_price)
            _, info = self.env.step(total_demand, {key: value.order_qty for key, value in decisions.items()})
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
                    "rnd_cost", "handling_cost", "profit",
                )
            } | {"cash": end["cash"]})
        # P4b fix: exits are deterministic year-end events; cash freezes
        # from the following tick after the configured grace period.
        self._apply_bankruptcy(year + 1)
        state.global_day = global_day
        state.year = year + 1

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
                year=year, firm_id=firm.id, revenue=summary.revenue,
                profit=summary.profit, market_share=retailer_shares.get(firm.id, 0.0),
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
        firm.employees = max(5, firm.employees + strategy.hiring_plan)
        runtime = self.env.runtimes[firm.id]
        runtime.wage_level = firm.wage_level
        runtime.employees = firm.employees

    def _apply_bankruptcy(self, completed_years: int) -> None:
        """P4b fix: close insolvent firms at year-end after the grace period."""
        cfg = self.config.bankruptcy
        if not cfg.enabled or completed_years < cfg.min_years_before_exit:
            return
        for firm_id, runtime in self.env.runtimes.items():
            if runtime.active and runtime.cash < cfg.cash_threshold:
                runtime.active = False
                self.exits[firm_id] = completed_years

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
