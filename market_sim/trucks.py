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

    def stock_total(self) -> int:
        return len(self.stock_used) + sum(len(v) for v in self.stock_new.values())


class TruckMarket:
    def __init__(self, config, geography, seed: int) -> None:
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
        for _ in range(self.cfg.dealer_start_count):
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
        return price * (1 - self.cfg.residual_value) / t.life_years + t.maintenance_rate * price

    # -- fleet use ---------------------------------------------------------
    def capacity(self, firm_id: str) -> float:
        return sum(self.types[t.type].capacity * (1 - t.downtime_days / self.days)
                   for t in self.fleets.get(firm_id, []))

    def has_fleet(self, firm_id: str) -> bool:
        return bool(self.fleets.get(firm_id))

    def try_ship(self, firm_id: str, units: float) -> bool:
        if self.used_today.get(firm_id, 0.0) + units <= self.capacity(firm_id):
            self.used_today[firm_id] = self.used_today.get(firm_id, 0.0) + units
            return True
        return False

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
        res = self.cfg.residual_value
        for fid in sorted(self.fleets):
            runtime = env.runtimes.get(fid)
            if runtime is None or not runtime.active:
                continue
            for truck in self.fleets[fid]:
                dep = 0.0
                floor = truck.purchase_price * res
                if truck.book_value > floor:
                    dep = min(truck.book_value - floor,
                              truck.purchase_price * (1 - res) / (self.types[truck.type].life_years * self.days))
                    truck.book_value -= dep
                runtime.fixed_cost += dep + truck.maint_daily
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
        return [self.dealers[d] for d in sorted(self.dealers) if self.dealers[d].active]

    def _restock(self, env) -> None:
        names = list(self.types)
        for dealer in self._active_dealers():
            room = max(0, self.cfg.dealer_max_stock - len(dealer.stock_used))
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
                    dealer.cash -= price
                    dealer.stock_new[t].append(self._new_truck(t, dealer.id, price))
                    if "trucks" in env.commodity_bought:
                        env.commodity_bought["trucks"] += 1.0

    # -- yearly --------------------------------------------------------------
    def begin_year_end(self, runner, state) -> None:
        env = runner.env
        cfg = self.cfg
        self.price_history.append({
            "year": state.year, "level": round(env.commodity_level("trucks"), 4),
            "prices": {t: round(self.list_price(env, t), 2) for t in self.types}})
        for fid in [f for f in self.fleets if not env.runtimes[f].active]:
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
                            self._pend(fid, cash_cost=cost)
                            self.repairs.append({"year": state.year, "firm": fid, "type": truck.type,
                                                 "age": truck.age, "cost": round(cost, 2)})
                            self._event(state, fid, "truck_repaired",
                                        f"{t.label} repariert, Kosten {chf(cost)}, {t.repair_days} Tage Ausfall")
                if reason:
                    cost = cfg.disposal_share * price
                    self._pend(fid, cash_cost=cost)
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
        dealer.cash -= price
        dealer.taken_back_year += 1
        self.fleets[firm.id].remove(truck)
        truck.owner, truck.cost_basis = dealer.id, price
        dealer.stock_used.append(truck)
        label = self.types[truck.type].label
        self.occasions.append({"year": state.year, "firm": firm.id, "dealer": dealer.id, "type": truck.type,
                               "age": truck.age, "price": round(price, 2), "book_value": round(truck.book_value, 2)})
        self._event(state, firm.id, "truck_sold_used",
                    f"{label} (Alter {truck.age}) als Occasion verkauft an {dealer.name}, {chf(price)}")
        return True

    def _best_offer(self, env, type_name: str):
        cfg = self.cfg
        best = None
        life = self.types[type_name].life_years
        for dealer in self._active_dealers():
            if dealer.stock_new[type_name]:
                offer = (self.list_price(env, type_name) * (1 + dealer.margin), 0, dealer.id, dealer, False, None)
                best = min(best, offer, key=lambda o: o[:3]) if best else offer
            used = sorted((u for u in dealer.stock_used if u.type == type_name and u.age <= 0.5 * life),
                          key=lambda u: (u.age, u.id))
            if used:
                offer = (self.value(env, used[0]) * (1 + cfg.dealer_used_margin), 1, dealer.id, dealer, True, used[0])
                best = min(best, offer, key=lambda o: o[:3]) if best else offer
        return best

    def decide(self, runner, state, firm, shipped: float, own_variable: float, service_cost: float) -> None:
        env = runner.env
        cfg = self.cfg
        runtime = env.runtimes[firm.id]
        fleet = self.fleets.setdefault(firm.id, [])
        need = cfg.peak_factor * shipped / self.days
        cap_now = sum(self.types[t.type].capacity for t in fleet)
        existing = sum(self.annual_cost(env, t.type) for t in fleet)
        plan: list[str] = []
        remaining = need - cap_now
        while remaining > 0 and len(plan) < cfg.max_new_trucks_per_firm_year:
            fitting = [t for t in self.types.values() if t.capacity <= remaining]
            if fitting:
                pick = min(fitting, key=lambda t: self.annual_cost(env, t.name) / t.capacity)
            else:
                pick = min(self.types.values(), key=lambda t: t.capacity)
            plan.append(pick.name)
            remaining -= pick.capacity
        extra = sum(self.annual_cost(env, t) for t in plan)
        threshold = service_cost * (1 + cfg.switch_margin) if fleet else service_cost * (1 - cfg.switch_margin)
        want_own = shipped > 0 and own_variable + existing + extra < threshold
        for truck in fleet:
            t = self.types[truck.type]
            maint = t.maintenance_rate * self.list_price(env, truck.type)
            truck.maintained = runtime.cash > 0 and env.can_spend(firm.id, maint)
            truck.maint_daily = maint / self.days if truck.maintained else 0.0
        aged = lambda t: t.age >= cfg.sell_age_fraction * self.types[t.type].life_years
        old = sorted((t for t in fleet if (not want_own) or aged(t)), key=lambda t: (-t.age, t.id))
        for truck in old:
            if self._sell_to_dealer(env, state, firm, truck) and want_own:
                plan.insert(0, truck.type)
        if want_own:
            bought = 0
            for type_name in sorted(plan, key=lambda n: -self.types[n].capacity):
                if bought >= cfg.max_new_trucks_per_firm_year:
                    break
                offer = self._best_offer(env, type_name)
                if offer is None:
                    continue
                price, _, _, dealer, used, source = offer
                if runtime.cash < cfg.cash_cover * price or not env.can_spend(firm.id, price):
                    break
                if used:
                    dealer.stock_used.remove(source)
                    truck = source
                    dealer.sold_used_year += 1
                else:
                    truck = dealer.stock_new[type_name].pop(0)
                    dealer.sold_new_year += 1
                    dealer.sold_by_type_year[type_name] = dealer.sold_by_type_year.get(type_name, 0) + 1
                runtime.adjust_cash(-price, "lastwagen_kauf")
                dealer.cash += price
                dealer.revenue += price
                dealer.cogs += truck.cost_basis
                truck.owner, truck.purchase_price, truck.book_value = firm.id, price, price
                truck.maintained, truck.downtime_days = True, 0
                truck.maint_daily = self.types[type_name].maintenance_rate * self.list_price(env, type_name) / self.days
                self.fleets[firm.id].append(truck)
                bought += 1
                self.purchases.append({"year": state.year, "firm": firm.id, "dealer": dealer.id, "type": type_name,
                                       "used": used, "price": round(price, 2), "age": truck.age})
                self._event(state, firm.id, "truck_bought",
                            f"{self.types[type_name].label} gekauft ({'Occasion' if used else 'neu'}) "
                            f"bei {dealer.name}, {chf(price)}")
        mode = "own" if self.fleets[firm.id] else "service"
        if mode != firm.transport_mode:
            firm.transport_mode = mode
            self._event(state, firm.id, "transport_switch",
                        "jetzt eigene Flotte" if mode == "own" else "jetzt Transportdienst")

    def finish_year_end(self, runner, state) -> None:
        env = runner.env
        cfg = self.cfg
        index = runner.long_run.price_index
        for dealer in self._active_dealers():
            stock = dealer.stock_used + [t for v in dealer.stock_new.values() for t in v]
            dealer.storage_cost = cfg.dealer_storage_rate * sum(t.cost_basis for t in stock)
            dealer.operating_cost = cfg.dealer_operating_cost * index
            dealer.cash -= dealer.storage_cost + dealer.operating_cost
            dealer.profit = dealer.revenue - dealer.cogs - dealer.storage_cost - dealer.operating_cost
            dealer.loss_years = dealer.loss_years + 1 if dealer.profit < 0 else 0
            self.dealer_history.append({
                "year": state.year, "dealer": dealer.id, "name": dealer.name, "margin": round(dealer.margin, 4),
                "cash": round(dealer.cash, 2), "stock_new": sum(len(v) for v in dealer.stock_new.values()),
                "stock_used": len(dealer.stock_used), "sold_new": dealer.sold_new_year,
                "sold_used": dealer.sold_used_year, "taken_back": dealer.taken_back_year,
                "takeback_limit": math.floor(cfg.takeback_share * dealer.sold_prev_new),
                "revenue": round(dealer.revenue, 2), "profit": round(dealer.profit, 2), "active": True})
            if dealer.loss_years >= cfg.dealer_exit_loss_years:
                dealer.active = False
                dealer.stock_new = {t: [] for t in self.types}
                dealer.stock_used = []
                self._event(state, dealer.id, "truck_dealer_exit", f"{dealer.name} gibt auf")
        self._restock(env)
        u, v = self.rng.random(), self.rng.random()
        active = self._active_dealers()
        mean_profit = sum(d.profit for d in active) / len(active) if active else 0.0
        if not active or (len(active) < cfg.dealer_max_count
                          and u < cfg.dealer_entry_probability * (1.0 if mean_profit > 0 else 0.3)):
            lo, hi = cfg.dealer_margin
            dealer = self._new_dealer(state.year + 1, cfg.dealer_start_cash * index, lo + v * (hi - lo))
            self._event(state, dealer.id, "truck_dealer_entry", f"{dealer.name} startet als Lastwagenhändler")
            self._restock(env)
        for fid in sorted(self.fleets):
            for type_name in self.types:
                trucks = [t for t in self.fleets[fid] if t.type == type_name]
                if trucks:
                    self.fleet_history.append({
                        "year": state.year, "firm": fid, "type": type_name, "count": len(trucks),
                        "capacity": round(len(trucks) * self.types[type_name].capacity, 1),
                        "avg_age": round(sum(t.age for t in trucks) / len(trucks), 2),
                        "maintained": sum(t.maintained for t in trucks)})
        for dealer in self.dealers.values():
            dealer.sold_prev_new = dealer.sold_new_year
            dealer.sold_by_type_prev = dict(dealer.sold_by_type_year)
            dealer.sold_new_year = dealer.sold_used_year = dealer.taken_back_year = 0
            dealer.sold_by_type_year = {}
            dealer.revenue = dealer.cogs = 0.0

    def export(self) -> dict:
        return {
            "enabled": True,
            "types": [{"name": t.name, "label": t.label, "capacity": t.capacity, "price_factor": t.price_factor,
                       "life_years": t.life_years, "maintenance_rate": t.maintenance_rate}
                      for t in self.types.values()],
            "prices": self.price_history, "fleet": self.fleet_history, "purchases": self.purchases,
            "occasions": self.occasions, "disposals": self.disposals, "repairs": self.repairs,
            "dealers": self.dealer_history,
        }

