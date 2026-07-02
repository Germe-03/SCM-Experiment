"""S8 two-level simulation runner for the full market mode."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random

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

    def run(self, years: int) -> RunResult:
        if years < 0:
            raise ValueError("years must be non-negative")
        self.env.reset()
        summaries: list[dict[str, YearSummary]] = []
        annual_reports: list[dict[str, AnnualReport]] = []
        system_kpis: list[SystemKPIs] = []
        daily_series: dict[str, dict[str, list[float]]] = {
            firm.id: {
                "inventory": [], "backlog": [], "cash": [],
                "cumulative_profit": [],
                **({"consumer_units_sold": [], "demand_share": []}
                   if firm.stage == "retailer" else {}),
            }
            for firm in self._firms()
        }
        financial_breakdown = {firm.id: [] for firm in self._firms()}
        recent_demand = {firm.id: [] for firm in self._firms()}
        recent_sales = {firm.id: [] for firm in self._firms()}
        global_day = 0
        for year in range(years):
            previous = summaries[-1] if summaries else {}
            starts = self._financial_starts()
            financial_starts = self._financial_snapshot_all()
            history_starts = {
                firm.id: (len(self.env.inventory_history[firm.id]), len(self.env.backlog_history[firm.id]))
                for firm in self._firms()
            }
            price_totals = {firm.id: 0.0 for firm in self._firms()}
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
                utilization,
            ))
            reports, kpis = self._build_reports(
                year + 1, summaries[-1], price_totals, retailer_served,
                retailer_lost, stockout_days, utilization, daily_turnover,
                daily_quality, ordered_edges, shipped_edges, demand_series,
                factory_order_series,
                b2b_received, b2b_shipped,
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
                        "rnd_cost", "profit",
                    )
                } | {"cash": end["cash"]})
            # P4b fix: exits are deterministic year-end events; cash freezes
            # from the following tick after the configured grace period.
            self._apply_bankruptcy(year + 1)
        return RunResult(
            years=years, network=self.network, yearly_summaries=summaries,
            final_result=self.env.get_result(), annual_reports=annual_reports,
            system_kpis=system_kpis,
            daily_series=daily_series, days_total=global_day,
            financial_breakdown=financial_breakdown,
        )

    def _build_reports(
        self, year, summaries, prices, served, lost, stockouts, utilization,
        turnover, qualities, ordered_edges, shipped_edges, demand_series,
        factory_order_series,
        b2b_received, b2b_shipped,
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
            target = max(0.0, min(1.0, 0.5 * fill + 0.5 * average_quality))
            speed = self.config.reputation.reputation_adjust_speed
            firm.reputation = max(0.0, min(1.0, firm.reputation + speed * (target - firm.reputation)))
            problems = []
            capacity_utilization = sum(utilization[firm.id]) / len(utilization[firm.id])
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
                average_sell_price=prices[firm.id] / days,
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
        for runtime in self.env.runtimes.values():
            if runtime.active and runtime.cash < cfg.cash_threshold:
                runtime.active = False

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
                "profit": float(getattr(runtime, "profit", 0.0)),
                "cash": float(getattr(runtime, "cash", 0.0)),
            }
            for firm_id, runtime in self.env.runtimes.items()
        }

    def _summarize_year(self, starts, history_starts, prices, served, lost, utilization):
        days = self.config.simulation.days_per_year
        result = {}
        for firm in self._firms():
            runtime = self.env.runtimes[firm.id]
            inv_start, back_start = history_starts[firm.id]
            inv = self.env.inventory_history[firm.id][inv_start:]
            back = self.env.backlog_history[firm.id][back_start:]
            revenue_start, profit_start = starts[firm.id]
            denominator = served[firm.id] + lost[firm.id]
            result[firm.id] = YearSummary(
                revenue=runtime.revenue - revenue_start,
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
            )
        return result

    @staticmethod
    def _moving_average(values: list[int], default: float) -> float:
        return sum(values) / len(values) if values else default
