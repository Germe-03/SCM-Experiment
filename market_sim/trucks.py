"""Phase 53: own truck fleets, used-truck trade and truck dealers."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from market_sim.kpi import chf


@dataclass
class Truck:
    id: str
    type: str
    age: int = 0
    owner: str = ""
    maintained: bool = True
    downtime_days: int = 0
    purchase_price: float = 0.0
    book_value: float = 0.0
    cost_basis: float = 0.0
    maint_daily: float = 0.0
    leased: bool = False
    service_dealer: str = ""
    service_until: int = 0
    bought_used: bool = False
    stock_since: int = 0
    surplus_years: int = 0


@dataclass
class Dealer:
    id: str
    name: str
    margin: float
    cash: float
    founded: int
    active: bool = True
    stock_new: dict = field(default_factory=dict)
    stock_used: list = field(default_factory=list)
    sold_new_year: int = 0
    sold_used_year: int = 0
    sold_prev_new: int = 0
    taken_back_year: int = 0
    sold_by_type_year: dict = field(default_factory=dict)
    sold_by_type_prev: dict = field(default_factory=dict)
    revenue: float = 0.0
    cogs: float = 0.0
    storage_cost: float = 0.0
    operating_cost: float = 0.0
    profit: float = 0.0
    loss_years: int = 0
    # Phase 56: the dealer is a firm; its cash flows reach the firm's accounts on the next day.
    rt: object = None
    pending: dict = field(default_factory=lambda: {"revenue": 0.0, "cogs": 0.0, "purchases": 0.0, "fixed": 0.0,
                                                   "wcogs": 0.0})
    revenue_new: float = 0.0
    revenue_used: float = 0.0
    revenue_workshop: float = 0.0
    workshop_jobs: int = 0
    workshop_jobs_prev: int = 0

    def stock_total(self) -> int:
        return len(self.stock_used) + sum(len(v) for v in self.stock_new.values())

    def buy_stock(self, price: float) -> None:
        """Pay for a truck going into stock (an asset, not an expense)."""
        self.cash -= price
        self.pending["purchases"] += price

    def sell_stock(self, price: float, basis: float) -> None:
        """Sale of a truck: revenue now, cost of goods sold at the purchase price."""
        self.cash += price
        self.revenue += price
        self.cogs += basis
        self.pending["revenue"] += price
        self.pending["cogs"] += basis

    def book_workshop(self, price: float, cost: float) -> None:
        """Workshop job: revenue is the price paid, parts and wages (cost) are paid out of it."""
        self.cash += price - cost
        self.revenue += price
        self.revenue_workshop += price
        self.cogs += cost
        self.pending["revenue"] += price
        self.pending["wcogs"] += cost

    def book_fixed(self, amount: float) -> None:
        self.cash -= amount
        self.pending["fixed"] += amount

    @property
    def firm_active(self) -> bool:
        return self.active and (self.rt is None or self.rt.active)


class TruckMarket:
    # Truck capacity in the config is units per day on this reference trip; the real daily
    # capacity is capacity x REF_KM unit-km, so a long trip uses up more of it.
    REF_KM = 100.0
    # Even a local trip uses at least this many km of capacity (loading, waiting, detours).
    MIN_KM = 20.0
    # A new truck must carry at least this share of its capacity as base load over the year.
    TARGET_UTILIZATION = 0.45
    # Below this many truck prices of cash a firm prefers leasing a new truck (if offered).
    LEASE_CASH_MULTIPLE = 4.0
    # An existing truck is kept while it still carries this share (a bit looser, no churn).
    KEEP_UTILIZATION = 0.35
    # Workshop: the firm pays cost x (1 + margin) to the dealer (parts and wages are the cost).
    WORKSHOP_MARGIN = 0.25
    # Repair jobs per year a dealer workshop handles without delay (grows with the load of the year before).
    WORKSHOP_CAP = 6
    WORKSHOP_GROWTH = 1.25
    # A busy workshop adds this many days of downtime to a repair.
    WORKSHOP_DELAY_DAYS = 10
    # Service contract: the buyer sticks to the selling dealer this many years.
    SERVICE_YEARS = 5
    # Used trucks: small firms and carriers take them up to this share of the life, large firms up to 0.5.
    USED_MAX_AGE_FRACTION = 0.8
    # A used truck bought as such is kept until this share of its life.
    USED_KEEP_FRACTION = 0.95
    # Stock older than this many years is scrapped by the dealer.
    STOCK_MAX_YEARS = 3
    # Calibration of the dealers (cost factors on the config values, number of active dealers).
    DEALER_OPERATING_FACTOR = 0.5
    DEALER_STORAGE_FACTOR = 0.5
    DEALER_MIN_ACTIVE = 3
    DEALER_MAX_ACTIVE = 5
    DEALER_EXIT_LOSS_YEARS = 8
    # Surplus trucks are sold only after this many years in a row without enough base load.
    SURPLUS_YEARS_TO_SELL = 2

    def __init__(self, config, geography, seed: int) -> None:
        self.leasing = None  # set by the runner when leasing is enabled
        self.last_takeback_price = 0.0
        self.config = config
        self.cfg = config.trucks
        self.geography = geography
        self.types = {t.name: t for t in self.cfg.types}
        self.days = config.simulation.days_per_year
        self.rng = random.Random(f"trucks-{seed}")
        self.fleets: dict[str, list[Truck]] = {}
        self.dealers: dict[str, Dealer] = {}
        self.pending: dict[str, list[float]] = {}
        self.used_today: dict[str, float] = {}
        self.purchases: list[dict] = []
        self.occasions: list[dict] = []
        self.disposals: list[dict] = []
        self.repairs: list[dict] = []
        self.fleet_history: list[dict] = []
        self.dealer_history: list[dict] = []
        self.price_history: list[dict] = []
        self._truck_counter = 0
        self._dealer_counter = 0
        self.carrier_owners: set[str] = set()
        self.workshop: list[dict] = []
        self._ws_acc: dict[tuple, float] = {}
        self._carrier_due: dict[str, float] = {}
        self._year = 1
        self._free_choice: Dealer | None = None
        for _ in range(max(self.cfg.dealer_start_count, self.DEALER_MIN_ACTIVE)):
            self._new_dealer(1, self.cfg.dealer_start_cash)

    # -- prices ----------------------------------------------------------
    def list_price(self, env, type_name: str) -> float:
        base = env.config.commodities.components.get("trucks", 0.0)
        return base * self.types[type_name].price_factor * env.commodity_level("trucks")

    def value(self, env, truck: Truck) -> float:
        t = self.types[truck.type]
        res = self.cfg.residual_value
        return self.list_price(env, truck.type) * max(res, 1 - (1 - res) * truck.age / t.life_years)

    def annual_cost(self, env, type_name: str) -> float:
        t = self.types[type_name]
        price = self.list_price(env, type_name)
        return price * (1 - self.cfg.residual_value) / t.life_years             + t.maintenance_rate * price * (1 + self.WORKSHOP_MARGIN)

    # -- fleet use ---------------------------------------------------------
    def capacity(self, firm_id: str) -> float:
        """Daily capacity of the fleet in unit-km."""
        return sum(self.types[t.type].capacity * self.REF_KM * (1 - t.downtime_days / self.days)
                   for t in self.fleets.get(firm_id, []))

    def has_fleet(self, firm_id: str) -> bool:
        return bool(self.fleets.get(firm_id))

    def try_ship(self, firm_id: str, units: float, km: float | None = None) -> bool:
        """Use up ``units x max(km, MIN_KM)`` unit-km of today's capacity (km default = REF_KM)."""
        distance = units * max(self.REF_KM if km is None else km, self.MIN_KM)
        if self.used_today.get(firm_id, 0.0) + distance <= self.capacity(firm_id):
            self.used_today[firm_id] = self.used_today.get(firm_id, 0.0) + distance
            return True
        return False

    def remove_truck(self, firm_id: str, truck_id: str):
        """Take a truck out of a fleet (e.g. repossession at bankruptcy); returns it or None."""
        fleet = self.fleets.get(firm_id, [])
        for truck in fleet:
            if truck.id == truck_id:
                fleet.remove(truck)
                return truck
        return None

    def take_back_leased(self, env, state, truck: Truck, dealer_id: str | None = None) -> bool:
        """A dealer takes a returned leased truck as a used one (counts to the take-back limit).

        The price (value x buyback_factor) goes to the lessor: see ``last_takeback_price``;
        the lessor books the payment itself.
        """
        cfg = self.cfg
        self.last_takeback_price = 0.0
        price = self.value(env, truck) * cfg.buyback_factor
        options = [d for d in self._active_dealers()
                   if d.taken_back_year < math.floor(cfg.takeback_share * d.sold_prev_new)
                   and d.cash >= price and d.stock_total() < cfg.dealer_max_stock + 4]
        if dealer_id is not None:
            options = [d for d in options if d.id == dealer_id] or options
        if not options:
            return False
        dealer = options[0]
        dealer.buy_stock(price)
        dealer.taken_back_year += 1
        old_owner = truck.owner
        if old_owner in self.fleets and truck in self.fleets[old_owner]:
            self.fleets[old_owner].remove(truck)
        truck.owner, truck.cost_basis, truck.leased = dealer.id, price, False
        self._to_stock(truck)
        dealer.stock_used.append(truck)
        self.last_takeback_price = price
        self.occasions.append({"year": state.year, "firm": old_owner, "dealer": dealer.id, "type": truck.type,
                               "age": truck.age, "price": round(price, 2), "book_value": round(truck.book_value, 2)})
        self._event(state, old_owner, "truck_returned",
                    f"{self.types[truck.type].label} (Leasing, Alter {truck.age}) an {dealer.name} "
                    f"zurückgenommen, {chf(price)}")
        return True

    def damage_multiplier(self, firm_id: str) -> float:
        fleet = self.fleets.get(firm_id)
        if not fleet:
            return 1.0
        unmaintained = sum(not t.maintained for t in fleet) / len(fleet)
        age = sum(t.age / self.types[t.type].life_years for t in fleet) / len(fleet)
        return 1 + self.cfg.damage_age_factor * (unmaintained + age)

    # -- daily bookings ------------------------------------------------------
    def daily(self, env) -> None:
        self.used_today = {}
        for fid in sorted(self.pending):
            runtime = env.runtimes.get(fid)
            cash_cost, book_loss = self.pending[fid]
            if runtime is not None and runtime.active:
                runtime.fixed_cost += cash_cost + book_loss
                runtime.adjust_cash(book_loss, "lastwagen_buchverlust")
        self.pending = {}
        self._refresh_free_choice()
        for did in sorted(self.dealers):
            dealer = self.dealers[did]
            rt = dealer.rt
            if rt is None or not rt.active:
                continue
            p = dealer.pending
            if any(p.values()):
                rt.revenue += p["revenue"]
                if p["revenue"]:
                    rt.record_items(rt.sold_items, "kunden", {"lastwagen": {"chf": p["revenue"], "units": 0}})
                rt.pay("rohstoffe", p["cogs"] + p.get("wcogs", 0.0))  # trucks, parts and wages
                rt.fixed_cost += p["fixed"]
                rt.adjust_cash(-p["purchases"] + p["cogs"], "lastwagenhandel:Lagerbestand")
                dealer.pending = {"revenue": 0.0, "cogs": 0.0, "purchases": 0.0, "fixed": 0.0, "wcogs": 0.0}
        res = self.cfg.residual_value
        for fid in sorted(self.fleets):
            runtime = env.runtimes.get(fid)
            if runtime is None or not runtime.active:
                continue
            for truck in self.fleets[fid]:
                dep = 0.0
                floor = truck.purchase_price * res
                if truck.book_value > floor and not truck.leased:  # a leased truck is the lessor's asset
                    dep = min(truck.book_value - floor,
                              truck.purchase_price * (1 - res) / (self.types[truck.type].life_years * self.days))
                    truck.book_value -= dep
                runtime.fixed_cost += dep + truck.maint_daily
                if truck.maint_daily > 0:
                    workshop = self.service_dealer_for(truck)
                    if workshop is not None:
                        self._book_workshop(workshop, fid, "wartung", truck.maint_daily)
                runtime.investment_depreciation = getattr(runtime, "investment_depreciation", 0.0) + dep
                if dep:
                    runtime.adjust_cash(dep, "lastwagen_abschreibung")

    # -- helpers -------------------------------------------------------------
    def _event(self, state, firm: str, event: str, details: str) -> None:
        state.events.append({"year": state.year, "day": self.days, "firm": firm,
                             "event": event, "details": details})

    def _pend(self, fid: str, cash_cost: float = 0.0, book_loss: float = 0.0) -> None:
        entry = self.pending.setdefault(fid, [0.0, 0.0])
        entry[0] += cash_cost
        entry[1] += book_loss

    def _charge(self, fid: str, amount: float) -> None:
        """A cost of a truck owner: firms pay it on the next day, carriers with their yearly bill."""
        if fid in self.carrier_owners:
            self._carrier_due[fid] = self._carrier_due.get(fid, 0.0) + amount
        else:
            self._pend(fid, cash_cost=amount)

    def _to_stock(self, truck: Truck) -> None:
        truck.service_dealer, truck.service_until = "", 0
        truck.bought_used, truck.surplus_years = False, 0
        truck.stock_since = self._year

    def _refresh_free_choice(self) -> None:
        active = [d for d in self._active_dealers() if d.firm_active]
        self._free_choice = min(active, key=lambda d: (d.margin, d.id)) if active else None

    def _contract_dealer(self, truck: Truck) -> Dealer | None:
        """The dealer bound by a running service contract, if still in business."""
        if not truck.service_dealer or truck.service_until < self._year:
            return None
        dealer = self.dealers.get(truck.service_dealer)
        return dealer if dealer is not None and dealer.active and dealer.firm_active else None

    def service_dealer_for(self, truck: Truck) -> Dealer | None:
        """Contract dealer; without a valid contract the cheapest margin (ties: lowest id)."""
        dealer = self._contract_dealer(truck)
        if dealer is not None:
            return dealer
        if self._free_choice is None or not self._free_choice.active or not self._free_choice.firm_active:
            self._refresh_free_choice()
        return self._free_choice

    def _assign_service(self, truck: Truck, dealer: Dealer, lease_years: int = 0) -> None:
        truck.service_dealer = dealer.id
        truck.service_until = self._year + max(self.SERVICE_YEARS, lease_years)

    def _workshop_cap(self, dealer: Dealer) -> int:
        return max(self.WORKSHOP_CAP, math.ceil(self.WORKSHOP_GROWTH * dealer.workshop_jobs_prev))

    def _book_workshop(self, dealer: Dealer, owner: str, kind: str, price: float) -> None:
        dealer.book_workshop(price, price / (1 + self.WORKSHOP_MARGIN))
        key = (self._year, dealer.id, owner, kind)
        self._ws_acc[key] = self._ws_acc.get(key, 0.0) + price

    def _repair_workshop(self, truck: Truck) -> tuple[Dealer | None, bool]:
        """Workshop for a repair and whether it is overloaded (longer downtime)."""
        dealer = self.service_dealer_for(truck)
        if dealer is None or dealer.workshop_jobs < self._workshop_cap(dealer):
            return dealer, False
        if self._contract_dealer(truck) is None:
            free = [d for d in self._active_dealers() if d.firm_active and d.workshop_jobs < self._workshop_cap(d)]
            if free:
                return min(free, key=lambda d: (d.margin, d.id)), False
        return dealer, True

    def _deliver(self, env, dealer: Dealer, type_name: str, price: float, used: bool, source, owner: str,
                 daily_maintenance: bool = True) -> Truck:
        """Hand a truck from the dealer stock to ``owner`` (the buyer payment is booked by the caller)."""
        if used:
            dealer.stock_used.remove(source)
            truck = source
            dealer.sold_used_year += 1
            dealer.revenue_used += price
        else:
            truck = dealer.stock_new[type_name].pop(0)
            dealer.sold_new_year += 1
            dealer.sold_by_type_year[type_name] = dealer.sold_by_type_year.get(type_name, 0) + 1
            dealer.revenue_new += price
        dealer.sell_stock(price, truck.cost_basis)
        truck.owner, truck.purchase_price, truck.book_value = owner, price, price
        truck.maintained, truck.downtime_days = True, 0
        truck.bought_used, truck.surplus_years = used, 0
        t = self.types[type_name]
        truck.maint_daily = (t.maintenance_rate * self.list_price(env, type_name) * (1 + self.WORKSHOP_MARGIN)
                             / self.days) if daily_maintenance else 0.0
        self._assign_service(truck, dealer)
        self.fleets.setdefault(owner, []).append(truck)
        return truck

    # -- interface for the Post and the couriers ------------------------------
    def buy_for_carrier(self, env, state, owner_id: str, type_name: str, pay):
        """Buy a truck (used first, else new) from the cheapest dealer for a carrier; ``pay(price)`` books it."""
        offer = self._best_offer(env, type_name, prefer_used=True)
        if offer is None:
            return None
        price, _, _, dealer, used, source = offer
        self.carrier_owners.add(owner_id)
        pay(price)
        truck = self._deliver(env, dealer, type_name, price, used, source, owner_id, daily_maintenance=False)
        self.purchases.append({"year": state.year, "firm": owner_id, "dealer": dealer.id, "type": type_name,
                               "used": used, "price": round(price, 2), "age": truck.age})
        return truck

    def carrier_maintenance(self, env, state, owner_id: str, pay) -> float:
        """Yearly maintenance plus the repairs (and scrapping) booked so far for all trucks of a carrier."""
        self.carrier_owners.add(owner_id)
        self._refresh_free_choice()
        total = self._carrier_due.pop(owner_id, 0.0)
        for truck in self.fleets.get(owner_id, []):
            dealer = self.service_dealer_for(truck)
            amount = (self.types[truck.type].maintenance_rate * self.list_price(env, truck.type)
                      * (1 + self.WORKSHOP_MARGIN))
            if dealer is not None:
                self._book_workshop(dealer, owner_id, "wartung", amount)
            total += amount
        if total > 0:
            pay(total)
        return total

    def _new_truck(self, type_name: str, owner: str, price: float) -> Truck:
        self._truck_counter += 1
        return Truck(id=f"lw_{self._truck_counter:04d}", type=type_name, owner=owner, cost_basis=price)

    def _new_dealer(self, founded: int, cash: float, margin: float | None = None) -> Dealer:
        self._dealer_counter += 1
        n = self._dealer_counter
        names = self.cfg.dealer_names
        name = names[n - 1] if n <= len(names) else f"Lastwagenhandel {n}"
        if margin is None:
            margin = self.rng.uniform(*self.cfg.dealer_margin)
        dealer = Dealer(id=f"haendler_{n:02d}", name=name, margin=margin, cash=cash, founded=founded,
                        stock_new={t: [] for t in self.types})
        self.dealers[dealer.id] = dealer
        return dealer

    def _active_dealers(self) -> list[Dealer]:
        for dealer in self.dealers.values():
            if dealer.active and dealer.rt is not None and not dealer.rt.active:
                # Closed by the runner (bankruptcy, takeover): the stock is gone with the firm.
                dealer.active = False
                dealer.stock_new = {t: [] for t in self.types}
                dealer.stock_used = []
        return [self.dealers[d] for d in sorted(self.dealers) if self.dealers[d].active]

    # -- Phase 56: dealers are firms ----------------------------------------
    def dealer_firm(self, dealer: Dealer, env):
        """The Firm record of a dealer (stage truck_dealer, outside the beverage chain)."""
        from market_sim.models import Firm
        regions = sorted(self.geography.regions)
        number = int(dealer.id.rsplit("_", 1)[1])
        scale = env.config.costs.initial_cash_scale or 1.0
        return Firm(
            id=dealer.id, name=dealer.name, stage="truck_dealer", archetype="reliable", tendency="reliable",
            cash=dealer.cash / scale, inventory=0, sell_price=1.0, quality_level=0.5, reputation=0.5,
            reliability=0.5, capacity=0, employees=0, wage_level=0.0, productivity_per_employee=1.0,
            r_and_d_level=0.0, r_and_d_budget=0.0, supplier_priority="balanced",
            category="lastwagen", region=regions[(number - 1) % len(regions)])

    def register_dealer(self, runner, state, dealer: Dealer) -> None:
        """Make the dealer a firm of the network (accounts, bank, stock market, reports)."""
        if dealer.rt is not None:
            return
        firm = self.dealer_firm(dealer, runner.env)
        runner.add_firm(firm, state, announce=False)
        dealer.rt = runner.env.runtimes[dealer.id]

    def register_all(self, runner, state) -> None:
        for did in sorted(self.dealers):
            if self.dealers[did].active:
                self.register_dealer(runner, state, self.dealers[did])

    def merge_dealers(self, target_id: str, buyer_id: str) -> None:
        """A dealer taken over by another: stock and book go to the buyer."""
        target, buyer = self.dealers.get(target_id), self.dealers.get(buyer_id)
        if target is None or buyer is None:
            return
        for name, trucks in target.stock_new.items():
            buyer.stock_new.setdefault(name, []).extend(trucks)
            for truck in trucks:
                truck.owner = buyer.id
        for truck in target.stock_used:
            truck.owner = buyer.id
        buyer.stock_used.extend(target.stock_used)
        target.stock_new = {t: [] for t in self.types}
        target.stock_used = []
        target.active = False

    def _restock(self, env) -> None:
        names = list(self.types)
        for dealer in self._active_dealers():
            # Stock follows the sales of the year before (an overfull yard only ages and gets scrapped).
            cap = min(self.cfg.dealer_max_stock, max(3, math.ceil(1.5 * dealer.sold_prev_new) + 1))
            room = max(0, cap - len(dealer.stock_used))
            weights = {t: dealer.sold_by_type_prev.get(t, 0) + 1 for t in names}
            total = sum(weights.values())
            raw = {t: room * weights[t] / total for t in names}
            target = {t: math.floor(raw[t]) for t in names}
            left = room - sum(target.values())
            for t in sorted(names, key=lambda x: (-(raw[x] - target[x]), names.index(x)))[:left]:
                target[t] += 1
            for t in names:
                price = self.list_price(env, t)
                while len(dealer.stock_new[t]) < target[t] and dealer.cash >= price > 0:
                    dealer.buy_stock(price)
                    new_truck = self._new_truck(t, dealer.id, price)
                    new_truck.stock_since = self._year
                    dealer.stock_new[t].append(new_truck)
                    if "trucks" in env.commodity_bought:
                        env.commodity_bought["trucks"] += 1.0

    # -- yearly --------------------------------------------------------------
    def begin_year_end(self, runner, state) -> None:
        env = runner.env
        cfg = self.cfg
        self._year = state.year
        self._refresh_free_choice()
        for dealer in self.dealers.values():
            if dealer.rt is not None and dealer.rt.active:
                dealer.cash = dealer.rt.cash  # the firm's account is the truth (interest, tax, loans)
        self.price_history.append({
            "year": state.year, "level": round(env.commodity_level("trucks"), 4),
            "prices": {t: round(self.list_price(env, t), 2) for t in self.types}})
        for fid in [f for f in self.fleets if f not in self.carrier_owners
                    and (env.runtimes.get(f) is None or not env.runtimes[f].active)]:
            del self.fleets[fid]
        for fid in sorted(self.fleets):
            keep = []
            for truck in self.fleets[fid]:
                r1, r2 = self.rng.random(), self.rng.random()
                t = self.types[truck.type]
                truck.age += 1
                truck.downtime_days = 0
                price = self.list_price(env, truck.type)
                reason = None
                if truck.age >= t.life_years:
                    reason = "Lebensende"
                else:
                    ratio = truck.age / t.life_years
                    p_fail = min(0.95, t.failure_base * (1 if truck.maintained else cfg.unmaintained_failure_multiplier)
                                 + cfg.age_failure_slope * ratio ** 2)
                    if r1 < p_fail:
                        p_total = min(0.95, (cfg.total_loss_base + cfg.age_total_loss * ratio)
                                      * (1 if truck.maintained else 2))
                        if r2 < p_total:
                            reason = "Totalschaden"
                        else:
                            cost = t.repair_share * price
                            truck.downtime_days = t.repair_days
                            workshop, busy = self._repair_workshop(truck)
                            if workshop is not None:
                                cost *= 1 + self.WORKSHOP_MARGIN
                                self._book_workshop(workshop, fid, "reparatur", cost)
                                workshop.workshop_jobs += 1
                                if busy:
                                    truck.downtime_days += self.WORKSHOP_DELAY_DAYS
                            self._charge(fid, cost)
                            self.repairs.append({"year": state.year, "firm": fid, "type": truck.type,
                                                 "age": truck.age, "cost": round(cost, 2)})
                            self._event(state, fid, "truck_repaired",
                                        f"{t.label} repariert, Kosten {chf(cost)}, {truck.downtime_days} Tage Ausfall")
                if reason:
                    cost = cfg.disposal_share * price
                    self._charge(fid, cost)
                    self.disposals.append({"year": state.year, "firm": fid, "type": truck.type,
                                           "age": truck.age, "cost": round(cost, 2), "reason": reason})
                    self._event(state, fid, "truck_scrapped",
                                f"{t.label}: {reason}, Entsorgung {chf(cost)}")
                else:
                    keep.append(truck)
            self.fleets[fid] = keep
        self._restock(env)

    def _sell_to_dealer(self, env, state, firm, truck: Truck) -> bool:
        cfg = self.cfg
        price = self.value(env, truck) * cfg.buyback_factor
        options = [d for d in self._active_dealers()
                   if d.taken_back_year < math.floor(cfg.takeback_share * d.sold_prev_new)
                   and d.cash >= price and d.stock_total() < cfg.dealer_max_stock + 4]
        if not options:
            return False
        dealer = options[0]
        runtime = env.runtimes[firm.id]
        runtime.adjust_cash(price, "lastwagen_verkauf")
        self._pend(firm.id, book_loss=truck.book_value - price)
        dealer.buy_stock(price)
        dealer.taken_back_year += 1
        self.fleets[firm.id].remove(truck)
        truck.owner, truck.cost_basis = dealer.id, price
        self._to_stock(truck)
        dealer.stock_used.append(truck)
        label = self.types[truck.type].label
        self.occasions.append({"year": state.year, "firm": firm.id, "dealer": dealer.id, "type": truck.type,
                               "age": truck.age, "price": round(price, 2), "book_value": round(truck.book_value, 2)})
        self._event(state, firm.id, "truck_sold_used",
                    f"{label} (Alter {truck.age}) als Occasion verkauft an {dealer.name}, {chf(price)}")
        return True

    def _best_offer(self, env, type_name: str, prefer_used: bool = False):
        """Cheapest offer; small firms, newcomers and carriers (``prefer_used``) take used trucks first
        and up to a higher age."""
        cfg = self.cfg
        news, useds = [], []
        life = self.types[type_name].life_years
        age_cap = (self.USED_MAX_AGE_FRACTION if prefer_used else 0.5) * life
        for dealer in self._active_dealers():
            if dealer.stock_new[type_name]:
                news.append((self.list_price(env, type_name) * (1 + dealer.margin), 0, dealer.id, dealer, False, None))
            used = sorted((u for u in dealer.stock_used if u.type == type_name and u.age <= age_cap),
                          key=lambda u: (u.age, u.id))
            if used:
                useds.append((self.value(env, used[0]) * (1 + cfg.dealer_used_margin), 1, dealer.id, dealer, True,
                              used[0]))
        pool = useds if (prefer_used and useds) else news + useds
        return min(pool, key=lambda o: o[:3]) if pool else None

    def decide(self, runner, state, firm, shipped: float, own_variable: float, service_cost: float,
               mean_km: float | None = None) -> None:
        """Fleet size by base load: every truck must carry enough to beat the Post; the rest goes with the Post.

        ``own_variable`` and ``service_cost`` are yearly costs of shipping everything own or with the Post.
        """
        env = runner.env
        cfg = self.cfg
        runtime = env.runtimes[firm.id]
        fleet = self.fleets.setdefault(firm.id, [])
        mean_km = self.REF_KM if mean_km is None else max(mean_km, self.MIN_KM)
        margin = cfg.switch_margin
        base_load = shipped * mean_km / self.days  # unit-km per day, mean over the year
        saving = max(0.0, service_cost - own_variable) / (shipped * mean_km) if shipped > 0 else 0.0

        def cap_ukm(name: str) -> float:
            return self.types[name].capacity * self.REF_KM

        def worth(name: str, carried: float, factor: float) -> bool:
            return carried > 0 and self.annual_cost(env, name) < saving * carried * self.days * factor

        # Existing trucks stay while they still carry enough of the base load (leased ones: contract runs).
        covered = sum(cap_ukm(t.type) for t in fleet if t.leased)
        surplus: list[Truck] = []
        for truck in sorted((t for t in fleet if not t.leased), key=lambda t: (t.age, t.id)):
            c = cap_ukm(truck.type)
            carried = min(c, base_load - covered)
            if carried >= self.KEEP_UTILIZATION * c and worth(truck.type, carried, 1 + margin):
                covered += c
                truck.surplus_years = 0
            elif truck.surplus_years + 1 < self.SURPLUS_YEARS_TO_SELL:
                truck.surplus_years += 1  # hysteresis: wait one more year before selling
                covered += c
            else:
                surplus.append(truck)
        carriers = getattr(runner.env.geography, "carriers", None)
        locked = not fleet and carriers is not None and carriers.service_locked(firm.id, state.year)
        # Phase 54: a running transport contract with the Post or a courier is respected (no first truck).
        plan: list[str] = []
        while shipped > 0 and not locked and len(plan) < cfg.max_new_trucks_per_firm_year:
            remaining = base_load - covered
            fitting = [t for t in self.types.values()
                       if remaining >= self.TARGET_UTILIZATION * cap_ukm(t.name)
                       and worth(t.name, min(cap_ukm(t.name), remaining), 1 - margin)]
            if not fitting:
                break
            pick = min(fitting, key=lambda t: self.annual_cost(env, t.name) / t.capacity)
            plan.append(pick.name)
            covered += cap_ukm(pick.name)
        want_own = bool(plan) or len(fleet) > len(surplus)
        for truck in fleet:
            t = self.types[truck.type]
            maint = t.maintenance_rate * self.list_price(env, truck.type) * (1 + self.WORKSHOP_MARGIN)
            truck.maintained = runtime.cash > 0 and env.can_spend(firm.id, maint)
            truck.maint_daily = maint / self.days if truck.maintained else 0.0
        aged = lambda t: t.age >= ((self.USED_KEEP_FRACTION if t.bought_used else cfg.sell_age_fraction)
                                   * self.types[t.type].life_years)
        surplus_ids = {t.id for t in surplus}
        old = sorted((t for t in fleet if not t.leased and (t.id in surplus_ids or aged(t))),
                     key=lambda t: (-t.age, t.id))
        for truck in old:
            if self._sell_to_dealer(env, state, firm, truck) and truck.id not in surplus_ids:
                plan.insert(0, truck.type)  # an aged truck of the base load is replaced
        if plan:
            bought = 0
            for type_name in sorted(plan, key=lambda n: -self.types[n].capacity):
                if bought >= cfg.max_new_trucks_per_firm_year:
                    break
                small = not fleet or runtime.cash < self.LEASE_CASH_MULTIPLE * self.list_price(env, type_name)
                offer = self._best_offer(env, type_name, prefer_used=small)
                if offer is None:
                    continue
                price, _, _, dealer, used, source = offer
                lease = None
                strategy = runner.strategies.get(firm.id) if hasattr(runner, "strategies") else None
                risk = strategy.risk_tolerance if strategy is not None else 0.5
                if self.leasing is not None and not used and runtime.cash < self.LEASE_CASH_MULTIPLE * price:
                    # Phase 57: a firm with little cash leases a new truck instead of tying up its cash.
                    lease = self.leasing.offer(env, firm.id, price, self.types[type_name].life_years,
                                               env.policy_rate(), risk)
                if lease is None and not env.arrange_funding(firm.id, price, "truck", cfg.cash_cover, state):
                    if self.leasing is None:
                        break
                    lease = self.leasing.offer(env, firm.id, price, self.types[type_name].life_years,
                                               env.policy_rate(), risk)
                    if lease is None:
                        break
                if lease is None:
                    runtime.adjust_cash(-price, "lastwagen_kauf")
                truck = self._deliver(env, dealer, type_name, price, used, source, firm.id)
                if lease is not None:
                    truck.leased = True
                    self.leasing.start(env, state, firm.id, truck, dealer, lease)
                    self._assign_service(truck, dealer, int(getattr(lease, "years", 0) or 0))
                bought += 1
                self.purchases.append({"year": state.year, "firm": firm.id, "dealer": dealer.id, "type": type_name,
                                       "used": used, "price": round(price, 2), "age": truck.age})
                self._event(state, firm.id, "truck_bought",
                            f"{self.types[type_name].label} {'geleast' if lease is not None else 'gekauft'} "
                            f"({'Occasion' if used else 'neu'}) bei {dealer.name}, {chf(price)}")
        mode = "own" if self.fleets[firm.id] else "service"
        if mode != firm.transport_mode:
            firm.transport_mode = mode
            self._event(state, firm.id, "transport_switch",
                        "jetzt eigene Flotte" if mode == "own" else "jetzt Transportdienst")

    def finish_year_end(self, runner, state) -> None:
        env = runner.env
        cfg = self.cfg
        index = runner.long_run.price_index
        contracts: dict[str, int] = {}
        for fleet in self.fleets.values():
            for truck in fleet:
                if truck.service_dealer and truck.service_until >= state.year:
                    contracts[truck.service_dealer] = contracts.get(truck.service_dealer, 0) + 1
        exit_years = max(cfg.dealer_exit_loss_years, self.DEALER_EXIT_LOSS_YEARS)
        for dealer in self._active_dealers():
            # Stock that stays too long is scrapped (write-off at the purchase price plus disposal cost).
            for pile in [dealer.stock_used] + list(dealer.stock_new.values()):
                for truck in [t for t in pile if state.year - t.stock_since > self.STOCK_MAX_YEARS]:
                    pile.remove(truck)
                    dealer.sell_stock(0.0, truck.cost_basis)
                    dealer.book_fixed(cfg.disposal_share * self.list_price(env, truck.type))
                    self._event(state, dealer.id, "truck_scrapped",
                                f"{self.types[truck.type].label} (Lager, Alter {truck.age}) verschrottet")
            stock = dealer.stock_used + [t for v in dealer.stock_new.values() for t in v]
            dealer.storage_cost = cfg.dealer_storage_rate * self.DEALER_STORAGE_FACTOR * sum(t.cost_basis for t in stock)
            dealer.operating_cost = cfg.dealer_operating_cost * self.DEALER_OPERATING_FACTOR * index
            dealer.book_fixed(dealer.storage_cost + dealer.operating_cost)
            dealer.profit = dealer.revenue - dealer.cogs - dealer.storage_cost - dealer.operating_cost
            dealer.loss_years = dealer.loss_years + 1 if dealer.profit < 0 else 0
            self.dealer_history.append({
                "year": state.year, "dealer": dealer.id, "name": dealer.name, "margin": round(dealer.margin, 4),
                "cash": round(dealer.cash, 2), "stock_new": sum(len(v) for v in dealer.stock_new.values()),
                "stock_used": len(dealer.stock_used), "sold_new": dealer.sold_new_year,
                "sold_used": dealer.sold_used_year, "taken_back": dealer.taken_back_year,
                "takeback_limit": math.floor(cfg.takeback_share * dealer.sold_prev_new),
                "revenue": round(dealer.revenue, 2), "profit": round(dealer.profit, 2), "active": True,
                "revenue_new": round(dealer.revenue_new, 2), "revenue_used": round(dealer.revenue_used, 2),
                "revenue_workshop": round(dealer.revenue_workshop, 2), "workshop_jobs": dealer.workshop_jobs,
                "service_contracts": contracts.get(dealer.id, 0)})
            if dealer.loss_years >= exit_years:
                dealer.active = False
                dealer.stock_new = {t: [] for t in self.types}
                dealer.stock_used = []
                if dealer.rt is not None and dealer.rt.active:
                    runner.close_firm_now(dealer.id, state.year, state, "truck_dealer_exit", f"{dealer.name} gibt auf")
                else:
                    self._event(state, dealer.id, "truck_dealer_exit", f"{dealer.name} gibt auf")
        self._restock(env)
        u, v = self.rng.random(), self.rng.random()
        active = self._active_dealers()
        mean_profit = sum(d.profit for d in active) / len(active) if active else 0.0
        if len(active) < self.DEALER_MIN_ACTIVE or (
                len(active) < self.DEALER_MAX_ACTIVE
                and u < cfg.dealer_entry_probability * (1.0 if mean_profit > 0 else 0.3)):
            lo, hi = cfg.dealer_margin
            dealer = self._new_dealer(state.year + 1, cfg.dealer_start_cash * index, lo + v * (hi - lo))
            self._event(state, dealer.id, "truck_dealer_entry", f"{dealer.name} startet als Lastwagenhändler")
            self.register_dealer(runner, state, dealer)
            self._restock(env)
        for fid in sorted(self.fleets):
            for type_name in self.types:
                trucks = [t for t in self.fleets[fid] if t.type == type_name]
                if trucks:
                    self.fleet_history.append({
                        "year": state.year, "firm": fid, "type": type_name, "count": len(trucks),
                        "capacity": round(len(trucks) * self.types[type_name].capacity, 1),
                        "avg_age": round(sum(t.age for t in trucks) / len(trucks), 2),
                        "maintained": sum(t.maintained for t in trucks),
                        "kind": "carrier" if fid in self.carrier_owners else "firm"})
        for dealer in self.dealers.values():
            dealer.sold_prev_new = dealer.sold_new_year
            dealer.sold_by_type_prev = dict(dealer.sold_by_type_year)
            dealer.sold_new_year = dealer.sold_used_year = dealer.taken_back_year = 0
            dealer.sold_by_type_year = {}
            dealer.revenue = dealer.cogs = 0.0
            dealer.revenue_new = dealer.revenue_used = dealer.revenue_workshop = 0.0
            dealer.workshop_jobs_prev, dealer.workshop_jobs = dealer.workshop_jobs, 0
        for (year, dealer_id, owner, kind), amount in sorted(self._ws_acc.items()):
            self.workshop.append({"year": year, "dealer": dealer_id, "firm": owner, "kind": kind,
                                  "amount": round(amount, 2)})
        self._ws_acc = {}
        self._year = state.year + 1

    def export(self) -> dict:
        return {
            "enabled": True,
            "types": [{"name": t.name, "label": t.label, "capacity": t.capacity, "price_factor": t.price_factor,
                       "life_years": t.life_years, "maintenance_rate": t.maintenance_rate}
                      for t in self.types.values()],
            "prices": self.price_history, "fleet": self.fleet_history, "purchases": self.purchases,
            "occasions": self.occasions, "disposals": self.disposals, "repairs": self.repairs,
            "dealers": self.dealer_history, "workshop": self.workshop,
        }

