"""Independent multi-firm implementation of the seven-step flow mechanics."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor

from market_sim.config import MarketConfig, load_market_config
from market_sim.models import STAGES, SupplyNetwork
from market_sim.selection import select_supplier


CONSUMER_ID = "__consumer__"
INITIAL_ID = "__initial__"


def proportional_integer_allocation(total: int, requests: dict[str, int]) -> dict[str, int]:
    """Allocate integer units by largest remainder, with id-based tie-breaking."""

    positive = {key: value for key, value in requests.items() if value > 0}
    result = {key: 0 for key in requests}
    requested = sum(positive.values())
    shipped = min(max(0, total), requested)
    if not shipped:
        return result
    quotas = {key: shipped * value / requested for key, value in positive.items()}
    for key, quota in quotas.items():
        result[key] = floor(quota)
    remaining = shipped - sum(result.values())
    ranking = sorted(positive, key=lambda key: (-(quotas[key] - floor(quotas[key])), key))
    for key in ranking[:remaining]:
        result[key] += 1
    return result


@dataclass
class FirmRuntime:
    """Mutable flow state for one firm, including backlog by customer."""

    inventory: int = 12
    backlog: int = 0
    incoming_shipments: list[int] = field(default_factory=lambda: [0, 0])
    incoming_orders: list[dict[str, int]] = field(default_factory=lambda: [{}, {}])
    backlog_by_downstream: dict[str, int] = field(default_factory=dict)
    order_history: list[int] = field(default_factory=list)
    shipment_history: list[int] = field(default_factory=list)
    orders_received_history: list[int] = field(default_factory=list)
    cumulative_holding_cost: float = 0.0
    cumulative_backlog_cost: float = 0.0
    holding_cost: float = 0.5
    backlog_cost: float = 1.0
    consumer_units_sold: int = 0
    cumulative_consumer_units_sold: int = 0
    initial_cash: float = 0.0
    cash: float = 0.0
    revenue: float = 0.0
    purchase_cost: float = 0.0
    wage_cost: float = 0.0
    hiring_cost: float = 0.0
    rnd_spend: float = 0.0
    employees: int = 0
    wage_level: float = 0.0
    turnover_rate: float = 0.0
    quality_level: float = 0.0
    pending_rnd_effects: list[tuple[int, float]] = field(default_factory=list)

    @property
    def cumulative_cost(self) -> float:
        """Legacy S3 operating-cost metric (holding plus backlog only)."""
        return self.cumulative_holding_cost + self.cumulative_backlog_cost

    @property
    def profit(self) -> float:
        return self.revenue - (
            self.purchase_cost + self.cumulative_holding_cost
            + self.cumulative_backlog_cost + self.wage_cost
            + self.hiring_cost + self.rnd_spend
        )

    def receive_shipment(self) -> int:
        received = self.incoming_shipments.pop(0)
        self.inventory += received
        return received

    def receive_orders(self) -> dict[str, int]:
        orders = self.incoming_orders.pop(0)
        self.orders_received_history.append(sum(orders.values()))
        return orders

    def calculate_period_cost(self, daily_wage_cost: float | None = None) -> tuple[float, float]:
        holding = self.inventory * self.holding_cost
        backlog = self.backlog * self.backlog_cost
        self.cumulative_holding_cost += holding
        self.cumulative_backlog_cost += backlog
        # S6 decision: wage_level is monthly and one tick is one day.
        self.wage_cost += (
            self.employees * self.wage_level / 30
            if daily_wage_cost is None else daily_wage_cost
        )
        # S6 decision: negative cash is recorded; bankruptcy/exit is deferred.
        self.cash = self.initial_cash + self.profit
        return holding, backlog


@dataclass(frozen=True)
class FirmResult:
    avg_inventory: float
    avg_backlog: float
    cumulative_cost: float
    cumulative_consumer_units_sold: int = 0
    revenue: float = 0.0
    purchase_cost: float = 0.0
    wage_cost: float = 0.0
    hiring_cost: float = 0.0
    rnd_spend: float = 0.0
    holding_cost: float = 0.0
    backlog_cost: float = 0.0
    profit: float = 0.0
    cash: float = 0.0


@dataclass(frozen=True)
class MarketResult:
    periods_run: int
    total_cost: float
    firm_results: dict[str, FirmResult]
    cumulative_lost_sales: int = 0
    total_profit: float = 0.0
    total_cash: float = 0.0


class MarketEnvironment:
    """Seven-step market environment supporting competing firms at each stage."""

    def __init__(
        self, network: SupplyNetwork, initial_inventory: int | None = None,
        initial_pipeline: tuple[int, ...] | None = None,
        initial_orders: tuple[int, ...] | None = None,
        holding_cost: float | None = None, backlog_cost: float | None = None,
        horizon: int | None = None, config: MarketConfig | None = None,
        consumer_demand_mode: str = "equal_backlog",
        enforce_capacity: bool = False,
        enable_workforce: bool = False,
        enable_rnd: bool = False,
    ) -> None:
        self.network = network
        self.config = config or load_market_config()
        self.initial_inventory = initial_inventory
        lead_time = self.config.logistics.default_lead_time_days
        self.initial_pipeline = initial_pipeline or tuple(0 for _ in range(lead_time))
        self.initial_orders = initial_orders or tuple(0 for _ in range(lead_time))
        if len(self.initial_pipeline) != len(self.initial_orders):
            raise ValueError("initial shipment and order pipelines must have equal length")
        self.holding_cost = holding_cost if holding_cost is not None else self.config.costs.holding_cost_per_unit
        self.backlog_cost = backlog_cost if backlog_cost is not None else self.config.costs.backlog_cost_per_unit
        self.horizon = horizon if horizon is not None else self.config.total_simulation_days
        if consumer_demand_mode not in {"equal_backlog", "attractiveness_lost"}:
            raise ValueError(f"unknown consumer demand mode: {consumer_demand_mode!r}")
        self.consumer_demand_mode = consumer_demand_mode
        self.enforce_capacity = enforce_capacity
        self.enable_workforce = enable_workforce
        self.enable_rnd = enable_rnd
        # S6 decision: prices remain static until S8. Consumer-facing prices
        # are bounded through _market_price; dynamic strategy pricing is not
        # implemented here. Existing B2B firm-spec prices remain unchanged.
        self.period = 0
        self.cumulative_lost_sales = 0
        self.runtimes: dict[str, FirmRuntime] = {}
        self.inventory_history: dict[str, list[int]] = {}
        self.backlog_history: dict[str, list[int]] = {}
        self._orders_received_this_period: dict[str, int] = {}

    def reset(self) -> None:
        self.period = 0
        self.cumulative_lost_sales = 0
        self.runtimes = {}
        for stage in STAGES:
            for firm in self.network.firms_in(stage):
                inventory = firm.inventory if self.initial_inventory is None else self.initial_inventory
                initial_backlog = firm.backlog
                customers = sorted(
                    candidate.id
                    for candidate_stage in STAGES
                    for candidate in self.network.firms_in(candidate_stage)
                    if firm.id in candidate.suppliers
                )
                seeded_customer = customers[0] if len(customers) == 1 else INITIAL_ID
                backlog_map = {seeded_customer: initial_backlog} if initial_backlog else {}
                self.runtimes[firm.id] = FirmRuntime(
                    inventory=inventory, backlog=initial_backlog,
                    incoming_shipments=list(self.initial_pipeline),
                    incoming_orders=[({seeded_customer: qty} if qty else {}) for qty in self.initial_orders],
                    backlog_by_downstream=backlog_map, holding_cost=self.holding_cost,
                    backlog_cost=self.backlog_cost,
                    initial_cash=firm.cash, cash=firm.cash,
                    employees=firm.employees, wage_level=firm.wage_level,
                    quality_level=firm.quality_level,
                )
        self.inventory_history = {firm_id: [] for firm_id in self.runtimes}
        self.backlog_history = {firm_id: [] for firm_id in self.runtimes}
        self._orders_received_this_period = {firm_id: 0 for firm_id in self.runtimes}

    def step(self, total_consumer_demand: int, orders: dict[str, int]) -> tuple[bool, dict]:
        if not self.runtimes:
            raise RuntimeError("Must call reset() before step()")

        if self.enable_workforce:
            for firm_id in sorted(self.runtimes):
                self._update_turnover_rate(firm_id)

        # 1. Receive shipments.
        for runtime in self._ordered_runtimes():
            runtime.receive_shipment()
            runtime.incoming_shipments.append(0)

        # 2. S5 decision: in attractiveness_lost mode consumers buy immediately
        # after inbound shipments.  This makes the reduced retailer inventory
        # visible to the subsequent, otherwise unchanged, B2B fulfillment step.
        # Consumer demand never enters retailer backlog in this mode.
        consumer_sales = {firm.id: 0 for firm in self.network.firms_in("retailer")}
        lost_sales = 0
        demand_shares: dict[str, int] = {}
        if self.consumer_demand_mode == "attractiveness_lost":
            demand_shares, consumer_sales, lost_sales = self._fulfill_consumer_demand(
                total_consumer_demand
            )
            self.cumulative_lost_sales += lost_sales
        else:
            demand_shares = self._allocate_consumer_demand(total_consumer_demand)

        # 3. Receive B2B orders.  The classic mode injects consumer demand as an
        # external retailer order, preserving the S3 backlog/parity mechanics.
        received_by_firm: dict[str, dict[str, int]] = {}
        for firm_id in sorted(self.runtimes):
            runtime = self.runtimes[firm_id]
            if self.consumer_demand_mode == "equal_backlog" and firm_id in demand_shares:
                # Consumer demand is the retailer's current external order, not
                # an addition to the seeded B2B order pipeline (S3 parity).
                runtime.incoming_orders[0] = {CONSUMER_ID: demand_shares[firm_id]}
            received_by_firm[firm_id] = runtime.receive_orders()
            runtime.incoming_orders.append({})
            self._orders_received_this_period[firm_id] = sum(received_by_firm[firm_id].values())

        # 4. Fulfill independently per supplier, proportionally across customers.
        shipped_this_period: dict[str, dict[str, int]] = {}
        for supplier_id in sorted(self.runtimes):
            runtime = self.runtimes[supplier_id]
            requested = dict(runtime.backlog_by_downstream)
            for downstream_id, quantity in received_by_firm[supplier_id].items():
                requested[downstream_id] = requested.get(downstream_id, 0) + quantity
            # S6 decision: capacity is a per-tick B2B handling/throughput limit.
            available = runtime.inventory
            if self.enforce_capacity:
                available = min(available, self._effective_capacity(supplier_id))
            allocations = proportional_integer_allocation(available, requested)
            shipped = sum(allocations.values())
            runtime.inventory -= shipped
            runtime.backlog_by_downstream = {
                key: requested[key] - allocations.get(key, 0)
                for key in requested if requested[key] - allocations.get(key, 0) > 0
            }
            runtime.backlog = sum(runtime.backlog_by_downstream.values())
            runtime.shipment_history.append(shipped)
            shipped_this_period[supplier_id] = allocations
            for downstream_id, quantity in allocations.items():
                if downstream_id in self.runtimes:
                    price = self.network.firm(supplier_id).sell_price
                    runtime.revenue += quantity * price
                    self.runtimes[downstream_id].purchase_cost += quantity * price
                    self.runtimes[downstream_id].incoming_shipments[-1] += quantity

        # 4. Record post-fulfillment state.
        for firm_id, runtime in self.runtimes.items():
            self.inventory_history[firm_id].append(runtime.inventory)
            self.backlog_history[firm_id].append(runtime.backlog)

        # 5. Route each full order to one deterministically selected supplier.
        selected_suppliers: dict[str, str] = {}
        for stage in STAGES:
            for firm in sorted(self.network.firms_in(stage), key=lambda item: item.id):
                quantity = max(0, int(orders.get(firm.id, 0)))
                self.runtimes[firm.id].order_history.append(quantity)
                if stage == STAGES[-1]:
                    # S6 decision: factory production is capacity-limited only
                    # when the optional clamp is enabled.
                    if self.enforce_capacity:
                        quantity = min(quantity, self._effective_capacity(firm.id))
                    self.runtimes[firm.id].incoming_shipments[-1] += quantity
                    continue
                candidates = self.network.suppliers_of(firm.id)
                lead_times = {candidate.id: self.config.logistics.default_lead_time_days for candidate in candidates}
                supplier = select_supplier(firm, candidates, self.config.supplier_score_weights, lead_times)
                selected_suppliers[firm.id] = supplier.id
                queue = self.runtimes[supplier.id].incoming_orders[-1]
                queue[firm.id] = queue.get(firm.id, 0) + quantity

        # 6-7. Accumulate costs and advance time.
        for firm_id in sorted(self.runtimes):
            runtime = self.runtimes[firm_id]
            firm = self.network.firm(firm_id)
            daily_wage = None
            if self.enable_workforce:
                # S7 decision: headcount is refilled in the MVP; churn adds a
                # temporary productivity loss and a hiring cash cost.
                cfg = self.config.workforce
                runtime.hiring_cost += (
                    firm.employees * runtime.turnover_rate
                    * cfg.hiring_cost_per_employee
                )
                daily_wage = firm.employees * firm.wage_level / cfg.days_per_month * (
                    1 + (cfg.overtime_wage_premium - 1) * firm.overtime_level
                )
            if self.enable_rnd:
                self._apply_rnd(firm_id)
            runtime.calculate_period_cost(daily_wage)
        self.period += 1
        firm_financials = {
            firm_id: self._financial_snapshot(runtime)
            for firm_id, runtime in self.runtimes.items()
        }
        info = {
            "period": self.period,
            "total_cost": sum(r.cumulative_cost for r in self.runtimes.values()),
            "total_inventory": sum(r.inventory for r in self.runtimes.values()),
            "total_backlog": sum(r.backlog for r in self.runtimes.values()),
            "shipments": shipped_this_period,
            "selected_suppliers": selected_suppliers,
            "consumer_demand_shares": demand_shares,
            "consumer_units_sold": consumer_sales,
            "consumer_units_sold_total": sum(consumer_sales.values()),
            "lost_sales": lost_sales,
            "cumulative_lost_sales": self.cumulative_lost_sales,
            "firms": firm_financials,
            "total_profit": sum(r.profit for r in self.runtimes.values()),
            "total_cash": sum(r.cash for r in self.runtimes.values()),
        }
        return self.period >= self.horizon, info

    def _allocate_consumer_demand(self, total_demand: int) -> dict[str, int]:
        """Classic equal split used only by equal_backlog mode."""
        retailers = sorted(firm.id for firm in self.network.firms_in("retailer"))
        demand = max(0, int(total_demand))
        base, remainder = divmod(demand, len(retailers))
        # Equal shares have equal fractional remainders, so firm id resolves them.
        return {
            firm_id: base + (index < remainder)
            for index, firm_id in enumerate(retailers)
        }

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _consumer_price_score(self, sell_price: float) -> float:
        price_range = self.config.price.max - self.config.price.min
        return self._clamp(
            (self.config.price.max - sell_price) / price_range
            if price_range > 0 else 0.0
        )

    def _consumer_availability_score(self, inventory: int, reference: float) -> float:
        return self._clamp(inventory / max(1.0, reference))

    def _consumer_attractiveness(self, demand: int) -> dict[str, float]:
        """Return bounded S5 retailer attractiveness scores."""

        retailers = sorted(self.network.firms_in("retailer"), key=lambda firm: firm.id)
        reference = max(1.0, demand / len(retailers))
        weights = self.config.demand_attractiveness_weights
        scores: dict[str, float] = {}
        for firm in retailers:
            price_score = self._consumer_price_score(firm.sell_price)
            availability = self._consumer_availability_score(
                self.runtimes[firm.id].inventory, reference
            )
            scores[firm.id] = self._clamp(
                weights.price * price_score
                + weights.quality * self._clamp(self.runtimes[firm.id].quality_level)
                + weights.reputation * self._clamp(firm.reputation)
                + weights.availability * availability
            )
        return scores

    @staticmethod
    def _weighted_integer_allocation(total: int, weights: dict[str, float]) -> dict[str, int]:
        """Largest-remainder allocation with deterministic id tie-breaking."""

        result = {key: 0 for key in weights}
        total = max(0, int(total))
        weight_sum = sum(max(0.0, value) for value in weights.values())
        if not total or not weights:
            return result
        effective = weights if weight_sum > 0 else {key: 1.0 for key in weights}
        denominator = sum(effective.values())
        quotas = {key: total * effective[key] / denominator for key in effective}
        result.update({key: floor(quota) for key, quota in quotas.items()})
        remainder = total - sum(result.values())
        ranking = sorted(quotas, key=lambda key: (-(quotas[key] - floor(quotas[key])), key))
        for key in ranking[:remainder]:
            result[key] += 1
        return result

    def _fulfill_consumer_demand(
        self, total_demand: int
    ) -> tuple[dict[str, int], dict[str, int], int]:
        """Split, serve, and spill consumer demand once; return remaining loss."""

        demand = max(0, int(total_demand))
        attractiveness = self._consumer_attractiveness(demand)
        shares = self._weighted_integer_allocation(demand, attractiveness)
        sold = {firm_id: 0 for firm_id in shares}
        capacities = {firm.id: self._effective_capacity(firm.id) for firm in self.network.firms_in("retailer")}
        for firm_id, share in shares.items():
            runtime = self.runtimes[firm_id]
            served = min(share, runtime.inventory, capacities[firm_id])
            runtime.inventory -= served
            sold[firm_id] += served

        unmet = demand - sum(sold.values())
        eligible = {
            firm_id: attractiveness[firm_id]
            for firm_id in shares
            if self.runtimes[firm_id].inventory > 0 and sold[firm_id] < capacities[firm_id]
        }
        spill = self._weighted_integer_allocation(unmet, eligible)
        for firm_id, allocation in spill.items():
            runtime = self.runtimes[firm_id]
            extra = min(allocation, runtime.inventory, capacities[firm_id] - sold[firm_id])
            runtime.inventory -= extra
            sold[firm_id] += extra

        for firm_id, units in sold.items():
            runtime = self.runtimes[firm_id]
            runtime.consumer_units_sold = units
            runtime.cumulative_consumer_units_sold += units
            runtime.revenue += units * self._market_price(
                self.network.firm(firm_id).sell_price
            )
        return shares, sold, demand - sum(sold.values())

    def get_result(self) -> MarketResult:
        if not self.runtimes:
            raise RuntimeError("No simulation has been run")
        results = {
            firm_id: FirmResult(
                self._average(self.inventory_history[firm_id]),
                self._average(self.backlog_history[firm_id]),
                runtime.cumulative_cost,
                runtime.cumulative_consumer_units_sold,
                runtime.revenue, runtime.purchase_cost, runtime.wage_cost,
                runtime.hiring_cost, runtime.rnd_spend,
                runtime.cumulative_holding_cost, runtime.cumulative_backlog_cost,
                runtime.profit, runtime.cash,
            )
            for firm_id, runtime in self.runtimes.items()
        }
        return MarketResult(
            self.period, sum(result.cumulative_cost for result in results.values()),
            results, self.cumulative_lost_sales,
            sum(result.profit for result in results.values()),
            sum(result.cash for result in results.values()),
        )

    @staticmethod
    def _financial_snapshot(runtime: FirmRuntime) -> dict[str, float]:
        return {
            "revenue": runtime.revenue,
            "purchase_cost": runtime.purchase_cost,
            "wage_cost": runtime.wage_cost,
            "hiring_cost": runtime.hiring_cost,
            "rnd_spend": runtime.rnd_spend,
            "holding": runtime.cumulative_holding_cost,
            "backlog": runtime.cumulative_backlog_cost,
            "profit": runtime.profit,
            "cash": runtime.cash,
        }

    def _effective_capacity(self, firm_id: str) -> int:
        firm = self.network.firm(firm_id)
        if not self.enable_workforce:
            return max(0, int(firm.capacity))
        # S7 decision: labour/machines establish base capacity; overtime raises
        # it, while current-day churn temporarily reduces productivity.
        base = max(
            firm.capacity,
            round(firm.employees * firm.productivity_per_employee)
            + firm.machine_capacity,
        )
        overtime = 1 + self.config.workforce.overtime_capacity_coeff * firm.overtime_level
        churn = max(
            0.0,
            1 - self.config.workforce.productivity_churn_penalty
            * self.runtimes[firm_id].turnover_rate,
        )
        return max(0, round(base * overtime * churn))

    def _update_turnover_rate(self, firm_id: str) -> None:
        firm = self.network.firm(firm_id)
        cfg = self.config.workforce
        wage_factor = 1 + cfg.wage_turnover_coeff * (
            cfg.wage_reference - firm.wage_level
        ) / cfg.wage_reference
        daily_turnover = (cfg.base_annual_turnover / 365) * (
            1 + cfg.overtime_turnover_coeff * firm.overtime_level
        ) * wage_factor
        self.runtimes[firm_id].turnover_rate = max(
            0.0, min(0.05, daily_turnover)
        )

    def _apply_rnd(self, firm_id: str) -> None:
        """Apply S7 quality decay and effects whose configured lag has elapsed."""
        firm = self.network.firm(firm_id)
        runtime = self.runtimes[firm_id]
        cfg = self.config.rnd
        daily_spend = firm.r_and_d_budget / 365
        runtime.rnd_spend += daily_spend
        runtime.pending_rnd_effects.append(
            (self.period + cfg.lag_days, cfg.effect_per_chf * daily_spend)
        )
        maturity_day = self.period + 1
        matured = sum(effect for due, effect in runtime.pending_rnd_effects if due <= maturity_day)
        runtime.pending_rnd_effects = [
            (due, effect) for due, effect in runtime.pending_rnd_effects
            if due > maturity_day
        ]
        runtime.quality_level = max(
            0.0,
            min(cfg.quality_cap, runtime.quality_level - cfg.daily_quality_decay + matured),
        )

    def _market_price(self, price: float) -> float:
        """Clamp a consumer price to the configured S6 market bounds."""
        return max(self.config.price.min, min(self.config.price.max, price))

    def runtime_for_stage(self, stage: str) -> FirmRuntime:
        firms = self.network.firms_in(stage)
        if len(firms) != 1:
            raise ValueError(f"stage {stage!r} has {len(firms)} firms; access runtime by firm id")
        return self.runtimes[firms[0].id]

    def orders_received_this_period(self, firm_id: str) -> int:
        return self._orders_received_this_period.get(firm_id, 0)

    def _ordered_runtimes(self) -> list[FirmRuntime]:
        return [self.runtimes[firm.id] for stage in STAGES for firm in sorted(self.network.firms_in(stage), key=lambda item: item.id)]

    @staticmethod
    def _average(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0
