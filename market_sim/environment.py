"""Independent multi-firm implementation of the seven-step flow mechanics."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, floor
import random

from market_sim.config import MarketConfig, load_market_config
from market_sim.banking import BankingSystem, CentralBank, deposit_threshold
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
    # Cash flows that are not profit; cash is recomputed daily from profit plus these.
    cash_adjustment: float = 0.0
    # Phase 10: marketing spending (also booked in fixed_cost).
    marketing_cost: float = 0.0
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
    # Money flow: purchase cost per recipient (supplier id, "rohstoffe", "staat:<reason>").
    paid_to: dict[str, float] = field(default_factory=dict)
    paid_items: dict[str, dict[str, float]] = field(default_factory=dict)
    sold_items: dict[str, dict[str, float]] = field(default_factory=dict)
    # Cash flows outside the profit by reason ("staat:Gewinnsteuer", "uebernahme:<firm>", ...).
    cash_flows: dict[str, float] = field(default_factory=dict)
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
    negative_interest_cost: float = 0.0
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
        self.cash = self.initial_cash + self.profit + self.cash_adjustment
        return holding, backlog

    def adjust_cash(self, delta: float, reason: str = "sonstiges") -> None:
        """Book a cash flow outside the profit (taxes, fines, write-offs, purchase prices)."""
        self.cash_adjustment += delta
        self.cash += delta
        if delta:
            self.cash_flows[reason] = self.cash_flows.get(reason, 0.0) + delta

    @staticmethod
    def record_items(ledger: dict, partner: str, items: dict) -> None:
        """Accumulate observations only; never change stock, cash or random state."""
        for category, item in items.items():
            entry = ledger.setdefault(f"{partner}|{category}", {"chf": 0.0, "units": 0})
            entry["chf"] += item["chf"]
            entry["units"] += item["units"]

    def pay(self, recipient: str, amount: float, items: dict | None = None) -> None:
        """Book purchase cost and remember who received it."""
        self.purchase_cost += amount
        if amount:
            self.paid_to[recipient] = self.paid_to.get(recipient, 0.0) + amount
            self.record_items(self.paid_items, recipient, items if items is not None else
                              {"alle": {"chf": amount, "units": 0}})


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
        self.central_bank = CentralBank(self.config.central_bank)
        self.banking: BankingSystem | None = None
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
        if self.banking is not None:
            self.banking.remove_firm(firm_id, runtime.cash)
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
        if self.banking is not None:
            self.banking.add_firm(firm.id)
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
        # Phase 43: merged firms run less efficiently in year 1 and later pay lower fixed costs.
        self.merger_efficiency: dict[str, float] = {}
        self.merger_fixed_factor: dict[str, float] = {}
        self.price_index = 1.0
        self.component_factor: dict[str, dict[str, float]] = {}
        self.material_savings: dict[str, float] = {}
        self.wage_savings: dict[str, float] = {}
        self.wage_saving_ratio: dict[str, float] = {}
        # Phase 7: lasting savings from successful research projects.
        self.process_cost_factor: dict[str, float] = {}
        self.research = None
        # Phase 10: marketing hook and excise taxes per category (share of unit cost).
        self.marketing = None
        self.excise: dict[str, float] = {}
        self._wine_rng = random.Random(f"wine-{self.seed}")
        self.domestic_daily_demand = float(self.config.demand.daily_demand_units)
        self.runtimes = {}
        self._commodity_rng = random.Random(f"commodities-{self.seed}")
        self.commodity_log_index = {name: 0.0 for name in self.config.commodities.components}
        # Phase 38: market price level per commodity (share of base price), demand and history.
        self.commodity_price = {name: 1.0 for name in self.config.commodities.components}
        self.commodity_bought = {name: 0.0 for name in self.config.commodities.components}
        self.commodity_past_bought: list[dict[str, float]] = []
        self.commodity_history: list[dict] = [self._commodity_row()]
        # Phase 39: stock per firm and commodity, risk appetite and this year's purchase prices.
        self.commodity_stock: dict[str, dict[str, float]] = {}
        self.commodity_courage: dict[str, float] = {}
        self.commodity_spend: dict[str, dict[str, list[float]]] = {}
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
        self.banking = (BankingSystem(self.config.banking, self.seed, self.runtimes)
                        if self.config.banking.enabled else None)
        self._credit_profit_marks: dict[str, float] = {}
        self.credit_year = 1
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

        if self.banking is not None:
            self._credit_profit_marks = {fid: rt.profit for fid, rt in self.runtimes.items()}

        self._update_commodity_index()
        self._age_commodity_stock()
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
        # Phase 28: parcels a full carrier held back leave today.
        if self.geography is not None and self.geography.carriers is not None:
            self.geography.carriers.release(self)

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
            if self.banking is None:
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
                    if self.banking is not None and self.config.banking.block_purchases and quantity:
                        customer = self.network.firm(downstream_id)
                        def cost(units):
                            if not self.brand_book.categories_on:
                                return self._trade_value(units, price)
                            parcel = self.brand_book.take_for(customer, dict(runtime.stock), units)
                            return self._trade_value(1, self.brand_book.parcel_value(parcel, price))
                        budget = self.spending_budget(downstream_id, cost(quantity))
                        if cost(quantity) > budget:
                            low, high = 0, quantity
                            while low < high:
                                mid = (low + high + 1) // 2
                                if cost(mid) <= budget:
                                    low = mid
                                else:
                                    high = mid - 1
                            quantity = low
                            cancelled = requested[downstream_id] - quantity
                            self.runtimes[downstream_id].on_order = max(
                                0, self.runtimes[downstream_id].on_order - cancelled)
                            requested[downstream_id] = quantity
                            allocations[downstream_id] = quantity
                    trade_value = self._trade_value(quantity, price)
                    parcel = {}
                    delay = 0
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
                            delay = self.geography.last_delay
                        if delay:
                            # Phase 28: the carrier is full; the parcel leaves later, nothing is lost.
                            self.geography.carriers.hold(self.period + delay, downstream_id, dict(parcel), quantity)
                        else:
                            add_to_stock(self.runtimes[downstream_id].incoming_brands[-1], parcel)
                        if self.brand_book.categories_on:
                            trade_value = self._trade_value(1, self.brand_book.parcel_value(parcel, price))
                            # Wine and spirits cost more to handle, in line with their value.
                            runtime.handling_cost += self.config.costs.handling_cost_per_unit * (
                                self.brand_book.parcel_value(parcel, 1.0) - sum(parcel.values()))
                    runtime.revenue += trade_value
                    items = self.trade_items(parcel, trade_value)
                    self.runtimes[downstream_id].pay(supplier_id, trade_value, items)
                    runtime.record_items(runtime.sold_items, downstream_id, items)
                    if not delay:
                        self.runtimes[downstream_id].incoming_shipments[-1] += quantity
            if self.banking is not None:
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
                    quantity = self.affordable_units(firm.id, quantity, self.unit_production_cost(firm))
                    self._procure_and_book(firm, self.runtimes[firm.id], quantity)
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
                if self.banking is not None and self.config.banking.block_purchases and candidates and quantity:
                    factor = max((self.brand_book.value_factor(b) for b in self.brand_book.brands), default=1.0) if self.brand_book.categories_on else 1.0
                    unit_cost = max(self._trade_value(1, s.sell_price) for s in candidates) * factor
                    pending = self.runtimes[firm.id].on_order
                    affordable = self.affordable_units(firm.id, quantity + pending, unit_cost)
                    quantity = min(quantity, max(0, affordable - pending))
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
        if self.marketing is not None:
            self.marketing.daily(self)

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
            self.wage_savings[firm_id] = self.wage_savings.get(firm_id, 0.0) + daily_wage * self.wage_saving_ratio.get(firm_id, 0.0)
            self._apply_interest(runtime, firm_id)
            if self.banking is not None:
                self._credit_profit_marks[firm_id] = runtime.profit
        if self.banking is not None:
            policy_rate = (self.central_bank.policy_rate if self.config.central_bank.enabled
                           else self.config.bank.base_rate)
            self.banking.daily(self.runtimes, policy_rate)
            self._credit_profit_marks.clear()
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

    def spending_budget(self, firm_id: str, amount: float) -> float:
        if self.banking is None:
            return float("inf")
        balances = {fid: rt.cash + rt.profit - self._credit_profit_marks.get(fid, rt.profit)
                    for fid, rt in self.runtimes.items()}
        days = self.config.simulation.days_per_year
        day = min(days, self.period - (self.credit_year - 1) * days + 1)
        return self.banking.spending_limit(firm_id, self.runtimes, balances, amount, self.credit_year, day)

    def can_spend(self, firm_id: str, amount: float) -> bool:
        if self.banking is None:
            return True
        budget = self.spending_budget(firm_id, max(amount, 1e-9))
        return budget > 0 and amount <= budget

    def affordable_units(self, firm_id: str, quantity: int, unit_cost: float) -> int:
        if self.banking is None or not self.config.banking.block_purchases or quantity <= 0 or unit_cost <= 0:
            return quantity
        budget = self.spending_budget(firm_id, quantity * unit_cost)
        return min(quantity, max(0, int(budget / unit_cost)))

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

    def unit_production_cost(self, firm: Firm, quantity: int = 0) -> float:
        """Raw materials per unit; imports pay the foreign price, exchange rate and tariff."""
        cost = self.material_cost_per_unit(firm.id) * self.process_cost_factor.get(firm.id, 1.0)
        book = self.brand_book
        if book is not None and book.categories_on:
            cost *= book.category_value(firm.category)
        if firm.importer and book is not None and book.categories_on:
            imports = self.config.categories.imports
            cost *= imports.cost_factor * self.fx_rate * (1 + imports.tariff)
        # Phase 10: excise taxes raise the unit cost of a category.
        cost *= 1 + self.excise.get(firm.category, 0.0)
        factor = self.firm_material_factor.get(firm.id, 1.0)
        if quantity:
            self.material_savings[firm.id] = self.material_savings.get(firm.id, 0.0) + quantity * cost * (1 - factor)
        return cost * factor

    def _book_production(self, firm: Firm, runtime: FirmRuntime, amount: float) -> None:
        """Production cost split into excise tax, import duty and raw materials (see unit_production_cost)."""
        excise = self.excise.get(firm.category, 0.0)
        tax = amount * excise / (1 + excise)
        duty = 0.0
        if firm.importer and self.brand_book is not None and self.brand_book.categories_on:
            tariff = self.config.categories.imports.tariff
            duty = (amount - tax) * tariff / (1 + tariff)
        runtime.pay("staat:Alkoholsteuer", tax)
        runtime.pay("staat:Zoll", duty)
        runtime.pay("rohstoffe", amount - tax - duty)

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
        batch = self.affordable_units(firm.id, batch, self.unit_production_cost(firm))
        self._book_production(firm, runtime, batch * self.unit_production_cost(firm, batch))
        self.record_commodity_purchase(firm.id, batch)
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

    def trade_items(self, parcel: dict[str, int], amount: float) -> dict:
        """Split the actual delivered parcel by category and its share of value."""
        book = self.brand_book
        items = {}
        weights = {}
        for brand_id, units in parcel.items():
            if not units:
                continue
            category = book.brands[brand_id].category if book.categories_on else "alle"
            item = items.setdefault(category, {"chf": 0.0, "units": 0})
            item["units"] += units
            weights[category] = weights.get(category, 0.0) + units * book.value_factor(brand_id)
        total = sum(weights.values())
        remaining = amount
        for index, (category, weight) in enumerate(weights.items()):
            value = remaining if index == len(weights) - 1 else amount * weight / total
            items[category]["chf"] = value
            remaining -= value
        return items

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
                runtime.record_items(runtime.sold_items, "export", self.trade_items(
                    parcel, self._trade_value(1, book.parcel_value(parcel, price))))
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

    def _apply_interest(self, runtime: FirmRuntime, firm_id: str | None = None) -> None:
        """Book one day's net borrowing cost or deposit income."""
        cfg = self.config.bank
        if not cfg.enabled:
            return
        debt = max(0.0, -runtime.cash)
        base_rate, deposit_rate, negative_rate = cfg.base_rate, cfg.deposit_rate, cfg.negative_rate
        if self.config.central_bank.enabled:
            policy_rate = self.central_bank.policy_rate
            base_rate = policy_rate + cfg.loan_margin
            deposit_rate = max(0.0, policy_rate - cfg.deposit_spread)
            if policy_rate < 0:
                negative_rate = max(negative_rate, -policy_rate)
        if self.banking is not None:
            if firm_id is None:
                firm_id = next(fid for fid, rt in self.runtimes.items() if rt is runtime)
            base_rate = (self.central_bank.policy_rate if self.config.central_bank.enabled else cfg.base_rate)
            # Without any active bank (all failed) the old generic margin applies.
            base_rate += (self.banking.primary_bank(firm_id).margin if self.banking.accounts.get(firm_id)
                          else cfg.loan_margin)
        rate = min(cfg.max_rate, base_rate
                   + cfg.risk_premium_per_loss_year * runtime.consecutive_loss_years
                   + cfg.leverage_premium * min(1.0, debt / max(1.0, runtime.last_year_revenue)))
        cost = debt * rate / 365 if debt else -runtime.cash * deposit_rate / 365
        negative = 0.0
        if not debt and cfg.negative_interest_enabled:
            threshold = deposit_threshold(cfg, runtime, self.price_index)
            negative = max(0.0, runtime.cash - threshold) * negative_rate / 365
            cost = negative - min(runtime.cash, threshold) * deposit_rate / 365
            runtime.negative_interest_cost += negative
        if self.banking is not None:
            self.banking.book_interest(firm_id, debt, cost, negative)
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
        factor *= self.merger_efficiency.get(firm_id, 1.0)
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
        if not self.can_spend(firm_id, daily_spend * self.config.costs.personnel_cost_scale):
            daily_spend = 0.0
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

    def _commodity_row(self) -> dict:
        days = self.config.simulation.days_per_year
        return {"year": self.period // days + 1,
                "prices": {n: self.commodity_price[n] for n in sorted(self.commodity_price)},
                "bought": {n: self.commodity_bought[n] for n in sorted(self.commodity_bought)}}

    def record_commodity_purchase(self, firm_id: str, units: float, name: str | None = None) -> None:
        """Phase 38: a firm buys sim-units of one commodity (name) or of every one (one per produced unit).

        Phase 39: extra stock purchases land here too, so they feed the demand of the market.
        """
        if not self.config.commodities.market_enabled or units <= 0:
            return
        for item in ([name] if name else sorted(self.commodity_bought)):
            self.commodity_bought[item] += units
            spend = self.commodity_spend.setdefault(firm_id, {}).setdefault(item, [0.0, 0.0])
            spend[0] += units
            spend[1] += units * self.commodity_price.get(item, 1.0)

    def _commodity_reference(self, name: str) -> float:
        """Average market price of the last few finished years (0 = none yet)."""
        rows = self.commodity_history[:-1][-self.config.commodities.market_reference_years:]
        return sum(row["prices"][name] for row in rows) / len(rows) if rows else 0.0

    def _component_cost(self, firm_id: str, name: str) -> float:
        base = self.config.commodities.components.get(name, 0.0)
        return (self.material_cost_multiplier * base * self.commodity_level(name)
                * self.component_factor.get(firm_id, {}).get(name, 1.0))

    def _firm_commodity_snapshot(self, reset: bool) -> dict:
        out = {}
        for firm_id in sorted(set(self.commodity_stock) | set(self.commodity_spend)):
            spend = self.commodity_spend.get(firm_id, {})
            out[firm_id] = {
                "stock": {n: round(v, 1) for n, v in sorted(self.commodity_stock.get(firm_id, {}).items())},
                "avg_price": {n: (s[1] / s[0] if s[0] > 0 else None) for n, s in sorted(spend.items())},
                "units": {n: s[0] for n, s in sorted(spend.items())},
            }
        if reset:
            self.commodity_spend = {}
        return out

    def commodity_rows(self) -> list[dict]:
        """History for reports; the running year is closed with the current state."""
        rows = [dict(row) for row in self.commodity_history]
        if rows:
            rows[-1]["bought"] = dict(self.commodity_bought)
            rows[-1]["firms"] = self._firm_commodity_snapshot(False)
        return rows

    def _age_commodity_stock(self) -> None:
        """Daily: stock spoils and costs storage money."""
        cfg = self.config.commodities
        if not (cfg.market_enabled and cfg.stockpile_enabled):
            return
        days = self.config.simulation.days_per_year
        for firm_id in sorted(self.commodity_stock):
            runtime = self.runtimes.get(firm_id)
            if runtime is None or not runtime.active:
                continue
            stock = self.commodity_stock[firm_id]
            cost = 0.0
            for name in sorted(stock):
                stock[name] -= stock[name] * cfg.stock_spoilage_per_year.get(name, 0.0) / days
                cost += stock[name] * self._component_cost(firm_id, name) * cfg.stock_storage_cost_per_year / days
            runtime.pay("rohstoffe", cost)

    def _procure_and_book(self, firm: Firm, runtime: FirmRuntime, quantity: int) -> None:
        """Pay the raw materials of a production run; use the stock first and buy ahead when cheap."""
        cfg = self.config.commodities
        unit_cost = self.unit_production_cost(firm, quantity)
        amount = quantity * unit_cost
        if not (cfg.market_enabled and cfg.stockpile_enabled):
            self._book_production(firm, runtime, amount)
            self.record_commodity_purchase(firm.id, quantity)
            return
        material = self.material_cost_per_unit(firm.id)
        scale = unit_cost / material if material > 0 else 1.0
        stock = self.commodity_stock.setdefault(firm.id, {})
        for name in sorted(cfg.components):
            used = min(stock.get(name, 0.0), float(quantity))
            if used > 0:
                stock[name] -= used
                amount -= used * self._component_cost(firm.id, name) * scale
            self.record_commodity_purchase(firm.id, quantity - used, name)
        self._book_production(firm, runtime, max(0.0, amount))
        # Buy ahead of need when the price is below the recent average.
        courage = max(0.0, min(1.0, self.commodity_courage.get(firm.id, 0.5)))
        threshold = 1.0 - cfg.stock_discount_threshold * (1.0 - courage)
        daily = max(1, self._effective_capacity(firm.id))
        for name in sorted(cfg.components):
            reference = self._commodity_reference(name)
            if name in cfg.stock_unstorable or reference <= 0 or self.commodity_level(name) / reference >= threshold:
                continue
            target = daily * cfg.stock_days * (0.3 + 0.7 * courage)
            want = target - stock.get(name, 0.0)
            price = self._component_cost(firm.id, name) * scale
            if want < 1 or price <= 0:
                continue
            budget = max(0.0, runtime.cash) * cfg.stock_cash_share
            units = float(self.affordable_units(firm.id, int(want), price))
            units = min(units, budget / price)
            if units < 1:
                continue
            self._book_production(firm, runtime, units * price)
            self.record_commodity_purchase(firm.id, units, name)
            stock[name] = stock.get(name, 0.0) + units

    def _update_commodity_market(self) -> None:
        """Yearly: demand versus the recent average nudges the price lightly, inside the band."""
        cfg = self.config.commodities
        days = self.config.simulation.days_per_year
        if self.period == 0 or self.period % days:
            return
        self.commodity_history[-1]["bought"] = dict(self.commodity_bought)
        self.commodity_history[-1]["firms"] = self._firm_commodity_snapshot(True)
        past = self.commodity_past_bought[-cfg.market_reference_years:]
        for name in sorted(self.commodity_price):
            push = 0.0
            reference = sum(row[name] for row in past) / len(past) if past else 0.0
            if reference > 0:
                push = cfg.market_demand_strength * max(-1.0, min(1.0, self.commodity_bought[name] / reference - 1.0))
            shock = self._commodity_rng.gauss(0.0, cfg.market_annual_volatility)
            level = self.commodity_price[name] * exp(shock + push)
            self.commodity_price[name] = max(cfg.market_band_min, min(cfg.market_band_max, level))
        self.commodity_past_bought.append(dict(self.commodity_bought))
        self.commodity_bought = {name: 0.0 for name in self.commodity_bought}
        self.commodity_history.append(self._commodity_row())

    def _update_commodity_index(self) -> None:
        """Mean-reverting log-price shocks per raw material, every few days."""
        cfg = self.config.commodities
        if cfg.market_enabled:
            self._update_commodity_market()
            return
        if not cfg.components or cfg.index_volatility == 0 or self.period % cfg.index_update_days:
            return
        for name in sorted(self.commodity_log_index):
            shock = self._commodity_rng.gauss(0.0, cfg.index_volatility)
            self.commodity_log_index[name] = (
                (1 - cfg.index_mean_reversion) * self.commodity_log_index[name] + shock
            )

    def commodity_level(self, name: str) -> float:
        if self.config.commodities.market_enabled:
            return self.commodity_price.get(name, 1.0)
        return exp(self.commodity_log_index.get(name, 0.0))

    def material_cost_per_unit(self, firm_id: str | None = None) -> float:
        """Current raw-material cost of one produced sim-unit in real CHF."""
        return self.material_cost_multiplier * sum(
            cost * self.commodity_level(name) * self.component_factor.get(firm_id, {}).get(name, 1.0)
            for name, cost in self.config.commodities.components.items()
        )

    def _daily_fixed_cost(self, firm) -> float:
        cfg = self.config.fixed_costs
        base = max(firm.capacity, round(firm.employees * firm.productivity_per_employee)) + firm.machine_capacity
        factor = self.config.restaurants.fixed_cost_factor if (
            firm.channel == "restaurant" and self.config.restaurants.enabled) else 1.0
        factor *= self.merger_fixed_factor.get(firm.id, 1.0)
        return factor * (
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
