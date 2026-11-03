"""Independent multi-firm implementation of the seven-step flow mechanics."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, floor
import random

from market_sim.config import MarketConfig, load_market_config
from market_sim.models import STAGES, Firm, SupplyNetwork
from market_sim.selection import split_order, supplier_candidates
from market_sim.geography import Geography
from market_sim.brands import BrandBook, add_to_stock, largest_remainder, take_from_stock


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
    # P1 fix: ordered units not yet received, including goods in transit.
    on_order: int = 0
    backlog_by_downstream: dict[str, int] = field(default_factory=dict)
    # Phase 2: units per brand on hand and per brand in transit (parallel to incoming_shipments).
    stock: dict[str, int] = field(default_factory=dict)
    incoming_brands: list[dict[str, int]] = field(default_factory=list)
    # Phase 4: wine maturing in the cellar as (release day, brand, units, vintage bonus).
    maturing: list[tuple[int, str, int, float]] = field(default_factory=list)
    # Phase 6: last year's bases for offences and counters to measure them.
    wage_cost_last_year: float = 0.0
    purchase_cost_last_year: float = 0.0
    profit_last_year: float = 0.0
    wage_cost_mark: float = 0.0
    purchase_cost_mark: float = 0.0
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
    handling_cost: float = 0.0
    fixed_cost: float = 0.0
    employees: int = 0
    wage_level: float = 0.0
    turnover_rate: float = 0.0
    quality_level: float = 0.0
    pending_rnd_effects: list[tuple[int, float]] = field(default_factory=list)
    # P4b fix: inactive runtimes are shut down and financially frozen.
    active: bool = True
    negative_cash_years: int = 0
    interest_cost: float = 0.0
    last_year_revenue: float = 0.0
    consecutive_loss_years: int = 0
    credit_limit: float = 0.0
    consecutive_bad_years: int = 0
    last_strategy_change_year: int | None = None

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
            + self.handling_cost + self.fixed_cost + self.interest_cost
        )

    def receive_shipment(self) -> int:
        received = self.incoming_shipments.pop(0)
        self.inventory += received
        if self.incoming_brands:
            add_to_stock(self.stock, self.incoming_brands.pop(0))
        # P1 fix: receiving changes bookkeeping only; never allow drift below zero.
        self.on_order = max(0, self.on_order - received)
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
    handling_cost: float = 0.0
    holding_cost: float = 0.0
    backlog_cost: float = 0.0
    profit: float = 0.0
    cash: float = 0.0
    fixed_cost: float = 0.0
    interest_cost: float = 0.0


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
        enforce_capacity: bool = False,
        enable_workforce: bool = False,
        enable_rnd: bool = False,
        seed: int = 0,
    ) -> None:
        self.network = network
        self.seed = seed
        self.commodity_log_index: dict[str, float] = {}
        # Market events (e.g. a failed harvest) scale raw-material prices.
        self.material_cost_multiplier = 1.0
        self._commodity_rng = random.Random(f"commodities-{seed}")
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
        self.enforce_capacity = enforce_capacity
        self.enable_workforce = enable_workforce
        self.enable_rnd = enable_rnd
        # S6 decision: prices remain static until S8. Consumer-facing prices
        # are bounded through _market_price; dynamic strategy pricing is not
        # implemented here. Existing B2B firm-spec prices remain unchanged.
        self.period = 0
        self.cumulative_lost_sales = 0
        self.cancelled_units = 0
        self.runtimes: dict[str, FirmRuntime] = {}
        self.inventory_history: dict[str, list[int]] = {}
        self.backlog_history: dict[str, list[int]] = {}
        self._orders_received_this_period: dict[str, int] = {}

    def close_firm(self, firm_id: str) -> None:
        """Cancel everything still open with a firm that has left the market."""
        runtime = self.runtimes[firm_id]
        runtime.active = False
        for customer_id, owed in self._open_units_by_customer(firm_id).items():
            customer = self.runtimes.get(customer_id)
            if customer is not None:
                customer.on_order = max(0, customer.on_order - owed)
        runtime.incoming_orders = [{} for _ in runtime.incoming_orders]
        runtime.backlog_by_downstream = {}
        runtime.backlog = 0
        runtime.on_order = 0

    def add_firm(self, firm: Firm) -> FirmRuntime:
        """Register one firm and create all mutable runtime state."""

        self.network.add_firm(firm)
        if firm.stage == "factory" and not self.brand_book.brands_of(firm.id):
            self.brand_book.add_brand_for(firm)
        runtime = self._new_runtime(firm)
        self.runtimes[firm.id] = runtime
        self.inventory_history[firm.id] = []
        self.backlog_history[firm.id] = []
        self._orders_received_this_period[firm.id] = 0
        return runtime

    def supplier_candidates(self, firm_id: str) -> list[Firm]:
        """Resolve the firm's currently active upstream candidates."""

        active = {key for key, runtime in self.runtimes.items() if runtime.active}
        return supplier_candidates(
            self.network, self.network.firm(firm_id), active,
            dynamic=self.config.supplier_discovery.enabled,
        )

    def _open_units_by_customer(self, firm_id: str) -> dict[str, int]:
        """Units each customer ordered from this firm that were never shipped."""
        runtime = self.runtimes[firm_id]
        owed: dict[str, int] = {}
        for queue in runtime.incoming_orders:
            for customer_id, quantity in queue.items():
                owed[customer_id] = owed.get(customer_id, 0) + quantity
        for customer_id, quantity in runtime.backlog_by_downstream.items():
            owed[customer_id] = owed.get(customer_id, 0) + quantity
        return owed

    def reset(self) -> None:
        self.period = 0
        self.cumulative_lost_sales = 0
        self.cancelled_units = 0
        # Phase 3: temporary capacity cuts per stage as (stage, first day, last day, factor).
        self.capacity_windows: list[tuple[str, int, int, float]] = []
        # Phase 4: CHF per EUR, the wine weather and the domestic demand that sizes exports.
        self.fx_rate = self.config.categories.fx_start
        # Phase 6: producers cutting corners on ingredients pay less per unit.
        self.firm_material_factor: dict[str, float] = {}
        # Phase 7: lasting savings from successful research projects.
        self.process_cost_factor: dict[str, float] = {}
        self.research = None
        self._wine_rng = random.Random(f"wine-{self.seed}")
        self.domestic_daily_demand = float(self.config.demand.daily_demand_units)
        self.runtimes = {}
        self._commodity_rng = random.Random(f"commodities-{self.seed}")
        self.commodity_log_index = {name: 0.0 for name in self.config.commodities.components}
        self.material_cost_multiplier = 1.0
        firms = [f for stage in STAGES for f in self.network.firms_in(stage)]
        self.brand_book = BrandBook(self.config, firms)
        self.geography = Geography(self.config, firms, self.seed) if self.config.geography.enabled else None
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
                self.runtimes[firm.id] = self._new_runtime(
                    firm, inventory=inventory, backlog_map=backlog_map,
                    seeded_customer=seeded_customer,
                )
        self.inventory_history = {firm_id: [] for firm_id in self.runtimes}
        self.backlog_history = {firm_id: [] for firm_id in self.runtimes}
        self._orders_received_this_period = {firm_id: 0 for firm_id in self.runtimes}

    def _new_runtime(
        self, firm: Firm, *, inventory: int | None = None,
        backlog_map: dict[str, int] | None = None, seeded_customer: str = INITIAL_ID,
    ) -> FirmRuntime:
        """Build the runtime record shared by reset and mid-run registration."""

        initial_backlog = firm.backlog
        backlog_map = backlog_map or ({seeded_customer: initial_backlog} if initial_backlog else {})
        scaled_cash = firm.cash * self.config.costs.initial_cash_scale
        runtime = FirmRuntime(
            inventory=firm.inventory if inventory is None else inventory,
            backlog=initial_backlog,
            incoming_shipments=list(self.initial_pipeline),
            on_order=sum(self.initial_pipeline),
            incoming_orders=[
                ({seeded_customer: qty} if qty else {}) for qty in self.initial_orders
            ],
            backlog_by_downstream=backlog_map,
            holding_cost=self.holding_cost, backlog_cost=self.backlog_cost,
            initial_cash=scaled_cash, cash=scaled_cash,
            credit_limit=max(self.config.bank.credit_limit_min,
                             self.config.bank.credit_limit_initial_cash_fraction * scaled_cash),
            employees=firm.employees, wage_level=firm.wage_level,
            quality_level=firm.quality_level,
        )
        if firm.importer and self.brand_book.categories_on:
            extra = self.config.categories.imports.lead_days - len(runtime.incoming_shipments)
            if extra > 0:
                runtime.incoming_shipments = [0] * extra + runtime.incoming_shipments
        runtime.stock = self.brand_book.initial_stock(firm, runtime.inventory)
        book = self.brand_book
        if book.categories_on and firm.category == "wine" and not firm.importer:
            # The cellar already holds the vintages that mature in the coming years.
            harvest = self.config.categories.harvest_day
            for brand_id, units in book.production_mix(firm.id, runtime.inventory).items():
                for k in range(book.brands[brand_id].maturation_days // 365):
                    runtime.maturing.append((self.period + harvest + 365 * k, brand_id, units, 0.0))
        runtime.incoming_brands = [
            self.brand_book.initial_stock(firm, qty) for qty in runtime.incoming_shipments
        ]
        return runtime

    def step(self, total_consumer_demand: int, orders: dict[str, int]) -> tuple[bool, dict]:
        if not self.runtimes:
            raise RuntimeError("Must call reset() before step()")

        self._update_commodity_index()
        active_ids = {
            firm_id for firm_id, runtime in self.runtimes.items()
            if runtime.active
        }
        if self.enable_workforce:
            for firm_id in sorted(self.runtimes):
                if self.runtimes[firm_id].active:
                    self._update_turnover_rate(firm_id)

        if self.brand_book.categories_on:
            self._release_matured()

        # 1. Receive shipments.
        for runtime in self._ordered_runtimes():
            if not runtime.active:
                continue
            runtime.receive_shipment()
            runtime.incoming_shipments.append(0)
            runtime.incoming_brands.append({})

        # 2. Consumer classes buy right after inbound shipments; unmet demand is lost,
        # it never enters a retailer backlog.
        demand_shares, consumer_sales, lost_sales = self.brand_book.fulfill(self, total_consumer_demand)
        for firm_id, units in consumer_sales.items():
            runtime = self.runtimes[firm_id]
            runtime.consumer_units_sold = units
            runtime.cumulative_consumer_units_sold += units
        consumer_sales = {firm.id: consumer_sales.get(firm.id, 0) for firm in self.network.firms_in("retailer")}
        self.cumulative_lost_sales += lost_sales

        # 3. Receive B2B orders.
        received_by_firm: dict[str, dict[str, int]] = {}
        for firm_id in sorted(self.runtimes):
            runtime = self.runtimes[firm_id]
            if not runtime.active:
                received_by_firm[firm_id] = {}
                self._orders_received_this_period[firm_id] = 0
                continue
            received_by_firm[firm_id] = runtime.receive_orders()
            runtime.incoming_orders.append({})
            self._orders_received_this_period[firm_id] = sum(received_by_firm[firm_id].values())

        # 4. Fulfill independently per supplier, proportionally across customers.
        shipped_this_period: dict[str, dict[str, int]] = {}
        for supplier_id in sorted(self.runtimes):
            runtime = self.runtimes[supplier_id]
            if not runtime.active:
                shipped_this_period[supplier_id] = {}
                continue
            requested = {
                downstream_id: quantity
                for downstream_id, quantity in runtime.backlog_by_downstream.items()
                if downstream_id not in self.runtimes or downstream_id in active_ids
            }
            for downstream_id, quantity in received_by_firm[supplier_id].items():
                if downstream_id in self.runtimes and downstream_id not in active_ids:
                    continue
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
            self._cancel_stale_backlog(supplier_id)
            runtime.shipment_history.append(shipped)
            runtime.handling_cost += shipped * self.config.costs.handling_cost_per_unit
            shipped_this_period[supplier_id] = allocations
            for downstream_id, quantity in allocations.items():
                if downstream_id in self.runtimes:
                    price = self.network.firm(supplier_id).sell_price
                    trade_value = self._trade_value(quantity, price)
                    if quantity:
                        parcel = self.brand_book.take_for(
                            self.network.firm(downstream_id), runtime.stock, quantity)
                        if self.geography is not None:
                            destroyed = self.geography.ship(
                                self, self.network.firm(supplier_id), self.network.firm(downstream_id), parcel)
                            if destroyed:
                                # The shipper bears the loss; the customer reorders the missing units.
                                trade_value *= (quantity - destroyed) / quantity
                                self.runtimes[downstream_id].on_order = max(
                                    0, self.runtimes[downstream_id].on_order - destroyed)
                                quantity -= destroyed
                        add_to_stock(self.runtimes[downstream_id].incoming_brands[-1], parcel)
                        if self.brand_book.categories_on:
                            trade_value = self._trade_value(1, self.brand_book.parcel_value(parcel, price))
                            # Wine and spirits cost more to handle, in line with their value.
                            runtime.handling_cost += self.config.costs.handling_cost_per_unit * (
                                self.brand_book.parcel_value(parcel, 1.0) - sum(parcel.values()))
                    runtime.revenue += trade_value
                    self.runtimes[downstream_id].purchase_cost += trade_value
                    self.runtimes[downstream_id].incoming_shipments[-1] += quantity

        if self.brand_book.categories_on:
            self._export()

        # 4. Record post-fulfillment state.
        for firm_id, runtime in self.runtimes.items():
            self.inventory_history[firm_id].append(runtime.inventory)
            self.backlog_history[firm_id].append(runtime.backlog)

        # 5. P2 fix: split each order across all allowed suppliers.
        selected_suppliers: dict[str, str] = {}
        split_orders: dict[str, dict[str, int]] = {}
        for stage in STAGES:
            for firm in sorted(self.network.firms_in(stage), key=lambda item: item.id):
                if not self.runtimes[firm.id].active:
                    continue
                quantity = max(0, int(orders.get(firm.id, 0)))
                self.runtimes[firm.id].order_history.append(quantity)
                if stage == STAGES[-1]:
                    # S6 decision: factory production is capacity-limited only
                    # when the optional clamp is enabled.
                    if self.enforce_capacity:
                        quantity = min(quantity, self._effective_capacity(firm.id))
                    if self._harvest_producer(firm):
                        continue
                    self.runtimes[firm.id].purchase_cost += quantity * self.unit_production_cost(firm)
                    # P1 fix: a factory production start is its replenishment order.
                    self.runtimes[firm.id].on_order += quantity
                    self.runtimes[firm.id].incoming_shipments[-1] += quantity
                    if quantity:
                        add_to_stock(
                            self.runtimes[firm.id].incoming_brands[-1],
                            self.brand_book.production_mix(firm.id, quantity),
                        )
                    continue
                candidates = self.supplier_candidates(firm.id)
                allocations = self._split_by_category(firm, candidates, quantity)
                split_orders[firm.id] = allocations
                if allocations:
                    selected_suppliers[firm.id] = min(
                        allocations, key=lambda supplier_id: (-allocations[supplier_id], supplier_id)
                    )
                # P1 fix: include queued, not-yet-shipped supplier orders.
                self.runtimes[firm.id].on_order += sum(allocations.values())
                for supplier_id, split_quantity in allocations.items():
                    queue = self.runtimes[supplier_id].incoming_orders[-1]
                    queue[firm.id] = queue.get(firm.id, 0) + split_quantity

        if self.geography is not None:
            self.geography.daily(self)
        if self.research is not None:
            self.research.daily(self)

        # 6-7. Accumulate costs and advance time.
        for firm_id in sorted(self.runtimes):
            runtime = self.runtimes[firm_id]
            if not runtime.active:
                continue
            firm = self.network.firm(firm_id)
            scale = self.config.costs.personnel_cost_scale
            daily_wage = runtime.employees * runtime.wage_level / 30 * scale
            if self.enable_workforce:
                # S7 decision: headcount is refilled in the MVP; churn adds a
                # temporary productivity loss and a hiring cash cost.
                cfg = self.config.workforce
                runtime.hiring_cost += (
                    firm.employees * runtime.turnover_rate
                    * cfg.hiring_cost_per_employee * scale
                )
                daily_wage = firm.employees * firm.wage_level / cfg.days_per_month * (
                    1 + (cfg.overtime_wage_premium - 1) * firm.overtime_level
                ) * scale
            runtime.fixed_cost += self._daily_fixed_cost(firm)
            if self.enable_rnd:
                self._apply_rnd(firm_id)
            runtime.calculate_period_cost(daily_wage)
            self._apply_interest(runtime)
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
            "split_orders": split_orders,
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

    def _split_order(self, firm: Firm, candidates: list[Firm], quantity: int) -> dict[str, int]:
        lead_times = {candidate.id: self.config.logistics.default_lead_time_days for candidate in candidates}
        delivered = None
        geo = self.geography
        if geo is not None:
            # Phase 5: nearby suppliers deliver faster and cheaper.
            units = self.config.unit_scale.real_units_per_sim_unit
            lead_times = {c.id: geo.km(c, firm) / geo.cfg.km_per_lead_day for c in candidates}
            delivered = {c.id: c.sell_price + geo.unit_transport_cost(c, firm) / units for c in candidates}
        return split_order(
            firm, candidates, quantity, self.config.supplier_score_weights,
            lead_times, self.config.policy.concentration,
            active_firm_ids=None,
            priority_boost=self.config.policy.supplier_priority_boost,
            delivered_prices=delivered,
        )

    def _split_by_category(self, firm: Firm, candidates: list[Firm], quantity: int) -> dict[str, int]:
        """Phase 4: a distributor splits its order by category and buys each from its producers."""
        book = self.brand_book
        if not book.categories_on or firm.stage != "distributor":
            return self._split_order(firm, candidates, quantity)
        groups: dict[str, list[Firm]] = {}
        for candidate in candidates:
            groups.setdefault(candidate.category, []).append(candidate)
        weights = {c: book.global_weight.get(c, 0.0) for c in groups}
        allocations: dict[str, int] = {}
        for category, units in largest_remainder(quantity, weights).items():
            if units:
                for supplier_id, part in self._split_order(firm, groups[category], units).items():
                    allocations[supplier_id] = allocations.get(supplier_id, 0) + part
        return allocations

    def unit_production_cost(self, firm: Firm) -> float:
        """Raw materials per unit; imports pay the foreign price, exchange rate and tariff."""
        cost = (self.material_cost_per_unit() * self.firm_material_factor.get(firm.id, 1.0)
                * self.process_cost_factor.get(firm.id, 1.0))
        book = self.brand_book
        if not book.categories_on:
            return cost
        cost *= book.category_value(firm.category)
        if firm.importer:
            imports = self.config.categories.imports
            cost *= imports.cost_factor * self.fx_rate * (1 + imports.tariff)
        return cost

    def _harvest_producer(self, firm: Firm) -> bool:
        """Wineries press grapes once a year; the wine matures before it can be sold."""
        book = self.brand_book
        if not book.categories_on or firm.category != "wine" or firm.importer:
            return False
        cfg = self.config.categories
        days = self.config.simulation.days_per_year
        if self.period % days != min(cfg.harvest_day, days - 1):
            return True
        runtime = self.runtimes[firm.id]
        # Forecast from what was actually delivered; order books overstate demand.
        delivered = sum(runtime.shipment_history[-days:])
        yield_factor = max(0.3, self._wine_rng.gauss(1.0, cfg.yield_sd))
        batch = round(min(self._effective_capacity(firm.id) * days, delivered * cfg.wine_forecast_buffer) * yield_factor)
        runtime.purchase_cost += batch * self.unit_production_cost(firm)
        bonus = max(-0.1, min(0.1, (yield_factor - 1) * cfg.vintage_quality_slope))
        for brand_id, units in book.production_mix(firm.id, batch).items():
            brand = book.brands[brand_id]
            runtime.maturing.append((self.period + brand.maturation_days, brand_id, units, bonus))
        return True

    def _release_matured(self) -> None:
        book = self.brand_book
        for runtime in self.runtimes.values():
            if not runtime.maturing:
                continue
            due = [item for item in runtime.maturing if item[0] <= self.period]
            if not due:
                continue
            runtime.maturing = [item for item in runtime.maturing if item[0] > self.period]
            for _, brand_id, units, bonus in due:
                runtime.stock[brand_id] = runtime.stock.get(brand_id, 0) + units
                runtime.inventory += units
                book.brands[brand_id].vintage_bonus = bonus

    def _export(self) -> None:
        """Foreign demand buys good domestic brands; a weak franc helps exporters."""
        book = self.brand_book
        cfg = self.config.categories.exports
        if not cfg.enabled:
            return
        factory_price = self.config.stage_prices["factory"].base
        for category, share in sorted(cfg.share.items()):
            daily = self.domestic_daily_demand * book.base_share.get(category, 0.0)
            wanted = round(share * daily * self.fx_rate ** cfg.fx_elasticity)
            if wanted <= 0:
                continue
            sellers = {}
            for firm in self.network.firms_in("factory"):
                runtime = self.runtimes[firm.id]
                if not runtime.active or firm.importer or firm.category != category or runtime.inventory <= 0:
                    continue
                quality = runtime.quality_level
                if quality >= cfg.quality_threshold:
                    sellers[firm.id] = quality
            for firm_id, units in largest_remainder(wanted, sellers).items():
                runtime = self.runtimes[firm_id]
                units = min(units, runtime.inventory)
                if not units:
                    continue
                parcel = take_from_stock(runtime.stock, units)
                sent = sum(parcel.values())
                runtime.inventory -= sent
                price = factory_price * cfg.world_price_factor * self.fx_rate
                runtime.revenue += self._trade_value(1, book.parcel_value(parcel, price))
                runtime.handling_cost += book.parcel_value(parcel, self.config.costs.handling_cost_per_unit)
                book.export_units += sent

    def _cancel_stale_backlog(self, supplier_id: str) -> None:
        """Cancel open orders a slow supplier cannot serve within the limit."""
        days = self.config.policy.max_backlog_days
        runtime = self.runtimes[supplier_id]
        if days is None or not runtime.backlog_by_downstream:
            return
        limit = int(days * max(1, self._effective_capacity(supplier_id)))
        if runtime.backlog <= limit:
            return
        keep = proportional_integer_allocation(limit, runtime.backlog_by_downstream)
        for customer_id, owed in runtime.backlog_by_downstream.items():
            customer = self.runtimes.get(customer_id)
            if customer is not None:
                customer.on_order = max(0, customer.on_order - (owed - keep.get(customer_id, 0)))
        self.cancelled_units += runtime.backlog - limit
        runtime.backlog_by_downstream = {key: value for key, value in keep.items() if value > 0}
        runtime.backlog = sum(runtime.backlog_by_downstream.values())

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _consumer_price_score(self, sell_price: float) -> float:
        band = self.config.stage_prices["retailer"]
        price_range = band.max - band.min
        return self._clamp(
            (band.max - sell_price) / price_range
            if price_range > 0 else 0.0
        )

    def _consumer_availability_score(self, inventory: int, reference: float) -> float:
        return self._clamp(inventory / max(1.0, reference))

    def _trade_value(self, quantity: int, price_per_bottle: float) -> float:
        """Return the real-CHF value of a trade expressed in sim-units."""

        return (
            quantity
            * price_per_bottle
            * self.config.unit_scale.real_units_per_sim_unit
        )

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
                runtime.hiring_cost, runtime.rnd_spend, runtime.handling_cost,
                runtime.cumulative_holding_cost, runtime.cumulative_backlog_cost,
                runtime.profit, runtime.cash, runtime.fixed_cost, runtime.interest_cost,
            )
            for firm_id, runtime in self.runtimes.items()
        }
        return MarketResult(
            self.period, sum(result.cumulative_cost for result in results.values()),
            results, self.cumulative_lost_sales,
            sum(result.profit for result in results.values()),
            sum(result.cash for result in results.values()),
        )

    def _apply_interest(self, runtime: FirmRuntime) -> None:
        """Book one day's net borrowing cost or deposit income."""
        cfg = self.config.bank
        if not cfg.enabled:
            return
        debt = max(0.0, -runtime.cash)
        rate = min(cfg.max_rate, cfg.base_rate
                   + cfg.risk_premium_per_loss_year * runtime.consecutive_loss_years
                   + cfg.leverage_premium * min(1.0, debt / max(1.0, runtime.last_year_revenue)))
        cost = debt * rate / 365 if debt else -runtime.cash * cfg.deposit_rate / 365
        runtime.interest_cost += cost
        runtime.cash -= cost

    @staticmethod
    def _financial_snapshot(runtime: FirmRuntime) -> dict[str, float]:
        return {
            "revenue": runtime.revenue,
            "purchase_cost": runtime.purchase_cost,
            "wage_cost": runtime.wage_cost,
            "hiring_cost": runtime.hiring_cost,
            "rnd_spend": runtime.rnd_spend,
            "handling_cost": runtime.handling_cost,
            "fixed_cost": runtime.fixed_cost,
            "interest_cost": runtime.interest_cost,
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
        factor = 1.0
        for stage, start, end, strength in self.capacity_windows:
            if stage == firm.stage and start <= self.period <= end:
                factor *= strength
        return max(0, round(base * overtime * churn * factor))

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
        # Cash cost lives on the scaled money scale; the quality effect does not.
        runtime.rnd_spend += daily_spend * self.config.costs.personnel_cost_scale
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

    def _update_commodity_index(self) -> None:
        """Mean-reverting log-price shocks per raw material, every few days."""
        cfg = self.config.commodities
        if not cfg.components or cfg.index_volatility == 0 or self.period % cfg.index_update_days:
            return
        for name in sorted(self.commodity_log_index):
            shock = self._commodity_rng.gauss(0.0, cfg.index_volatility)
            self.commodity_log_index[name] = (
                (1 - cfg.index_mean_reversion) * self.commodity_log_index[name] + shock
            )

    def material_cost_per_unit(self) -> float:
        """Current raw-material cost of one produced sim-unit in real CHF."""
        return self.material_cost_multiplier * sum(
            cost * exp(self.commodity_log_index.get(name, 0.0))
            for name, cost in self.config.commodities.components.items()
        )

    def _daily_fixed_cost(self, firm) -> float:
        cfg = self.config.fixed_costs
        base = max(firm.capacity, round(firm.employees * firm.productivity_per_employee)) + firm.machine_capacity
        return (
            cfg.base_per_day.get(firm.stage, 0.0)
            + cfg.per_capacity_unit_per_day.get(firm.stage, 0.0) * base
        )

    def _market_price(self, price: float) -> float:
        """Clamp a consumer price to the configured S6 market bounds."""
        return max(self.config.price.min, min(self.config.price.max, price))

    def orders_received_this_period(self, firm_id: str) -> int:
        return self._orders_received_this_period.get(firm_id, 0)

    def _ordered_runtimes(self) -> list[FirmRuntime]:
        return [self.runtimes[firm.id] for stage in STAGES for firm in sorted(self.network.firms_in(stage), key=lambda item: item.id)]

    @staticmethod
    def _average(values: list[int]) -> float:
        return sum(values) / len(values) if values else 0.0
