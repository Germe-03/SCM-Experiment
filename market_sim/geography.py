"""Phase 5: regions, transport costs, own fleet or transport service, expansion and new sites."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from market_sim.kpi import chf
from market_sim.models import STAGES, Firm

if TYPE_CHECKING:
    from market_sim.environment import MarketEnvironment
    from market_sim.runner import RunState, SimulationRunner


class Geography:
    """Distances between sites, the yearly transport choice and capacity investments."""

    def __init__(self, config, firms: list[Firm], seed: int) -> None:
        self.cfg = config.geography
        self.regions = {r.name: r for r in self.cfg.regions}
        total = sum(r.population_share for r in self.cfg.regions) or 1.0
        self.population = {r.name: r.population_share / total for r in self.cfg.regions}
        self.rng = random.Random(f"geography-{seed}")
        self.fuel_index = 1.0
        self.transport_factor: dict[str, float] = {}
        # Investments under construction as (finish day, firm id, kind, region or units).
        self.projects: list[tuple[int, str, str, object]] = []
        # Depreciation still to book per firm as (daily amount, last day).
        self.depreciation: dict[str, list[tuple[float, int]]] = {}
        self.stats = {"transport_cost": 0.0, "damaged_units": 0, "expansions": 0, "new_sites": 0}
        # Phase 28: the Post (and couriers) instead of the anonymous service; None = old service.
        self.carriers = None
        # Delay in days of the last booked shipment (0 = normal lead time).
        self.last_delay = 0
        if getattr(config, "carriers", None) is not None and config.carriers.enabled:
            from market_sim.carriers import CarrierMarket
            from market_sim.couriers import CourierMarket
            market = CourierMarket if config.carriers.couriers.enabled else CarrierMarket
            self.carriers = market(config, self, seed)
        for index, firm in enumerate(sorted(firms, key=lambda f: (STAGES.index(f.stage), f.id))):
            if firm.region is None:
                firm.region = self._default_region(firm.stage, index)

    def _default_region(self, stage: str, index: int) -> str:
        """Spread firms over regions roughly in proportion to population."""
        names = sorted(self.population, key=lambda name: -self.population[name])
        return names[index % len(names)]

    def sites(self, firm: Firm) -> list[str]:
        return [firm.region or next(iter(self.regions))] + list(firm.extra_regions)

    def km(self, a: Firm, b: Firm) -> float:
        best = math.inf
        for ra in self.sites(a):
            for rb in self.sites(b):
                pa, pb = self.regions[ra], self.regions[rb]
                best = min(best, math.hypot(pa.x - pb.x, pa.y - pb.y) * self.cfg.road_factor + self.cfg.local_km)
        return best

    def rate(self, firm: Firm) -> float:
        base = self.cfg.service_rate if firm.transport_mode == "service" else self.cfg.own_rate
        return base * self.fuel_index * self.transport_factor.get(firm.id, 1.0)

    def unit_transport_cost(self, supplier: Firm, customer: Firm) -> float:
        if self.carriers is not None and supplier.transport_mode == "service":
            return self.km(supplier, customer) * (self.carriers.rate(supplier, customer)
                                                  * self.fuel_index * self.transport_factor.get(supplier.id, 1.0))
        return self.km(supplier, customer) * self.rate(supplier)

    def ship(self, env: MarketEnvironment, supplier: Firm, customer: Firm, parcel: dict[str, int]) -> int:
        """Book transport cost; an own fleet may damage goods. Returns destroyed units."""
        self.last_delay = 0
        units = sum(parcel.values())
        if not units:
            return 0
        cost = units * self.unit_transport_cost(supplier, customer)
        runtime = env.runtimes[supplier.id]
        runtime.handling_cost += cost
        self.stats["transport_cost"] += cost
        roll = self.rng.random()
        damage_probability = self.cfg.damage_probability
        if self.carriers is not None:
            km = self.km(supplier, customer)
            if supplier.transport_mode == "service":
                self.last_delay = self.carriers.book(env.period, supplier, customer, units, km, cost, self.fuel_index)
                damage_probability = self.carriers.damage_probability(supplier, customer)
            else:
                self.carriers.record_own(customer, units, km)
        if roll >= damage_probability or (supplier.transport_mode == "service" and self.carriers is None):
            return 0
        destroyed = max(1, round(units * self.cfg.damage_share))
        taken = 0
        for brand_id in sorted(parcel, key=lambda b: -parcel[b]):
            take = min(parcel[brand_id], destroyed - taken)
            parcel[brand_id] -= take
            taken += take
            if taken >= destroyed:
                break
        self.stats["damaged_units"] += taken
        return taken

    def daily(self, env: MarketEnvironment) -> None:
        """Fleet fixed costs and depreciation of finished investments."""
        if self.carriers is not None:
            self.carriers.daily(env)
        for firm_id, runtime in env.runtimes.items():
            if not runtime.active:
                continue
            firm = env.network.firm(firm_id)
            if firm.transport_mode == "own" and firm.stage != "retailer":
                runtime.fixed_cost += self.cfg.fleet_cost_per_day
            for amount, last in self.depreciation.get(firm_id, []):
                if env.period <= last:
                    runtime.fixed_cost += amount
                    runtime.investment_depreciation = getattr(runtime, "investment_depreciation", 0.0) + amount

    # -- yearly decisions -------------------------------------------------
    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        cfg = self.cfg
        env = runner.env
        days = runner.config.simulation.days_per_year
        fuel_roll = self.rng.gauss(0.0, 1.0)
        self.fuel_index = max(0.5, self.fuel_index * math.exp(cfg.fuel_volatility * fuel_roll))
        self._finish_projects(runner, state)
        summaries = state.summaries[-1]
        for firm in runner._firms():
            runtime = env.runtimes[firm.id]
            if not runtime.active or firm.stage == "retailer":
                continue
            self._choose_transport(runner, firm, summaries, state)
        # Only a tight stage invests: one busy firm alone would just take share from idle rivals.
        stage_use = {}
        for stage in STAGES:
            active = [f for f in runner.network.firms_in(stage) if env.runtimes[f.id].active and f.id in summaries]
            stage_use[stage] = (sum(summaries[f.id].capacity_utilization for f in active) / len(active)
                                if active else 0.0)
        for firm in runner._firms():
            runtime = env.runtimes[firm.id]
            if not runtime.active or firm.id not in summaries:
                continue
            if stage_use[firm.stage] < cfg.stage_utilization_min:
                continue
            self._invest(runner, firm, summaries[firm.id], state, days)
        self.depreciation = {k: [d for d in v if d[1] >= env.period] for k, v in self.depreciation.items()}
        if self.carriers is not None:
            self.carriers.year_end(runner, state)

    def _choose_transport(self, runner, firm, summaries, state) -> None:
        """Own fleet: fixed cost plus damage risk; service: dearer per km, no risk."""
        cfg = self.cfg
        env = runner.env
        shipped = sum(env.runtimes[firm.id].shipment_history[-runner.config.simulation.days_per_year:])
        if not shipped:
            return
        customers = [f for f in runner._firms() if env.runtimes[f.id].active and f.stage == runner.network.downstream_stage(firm.stage)]
        mean_km = sum(self.km(firm, c) for c in customers) / len(customers) if customers else cfg.local_km
        unit_value = runner.config.stage_prices[firm.stage].base * runner.config.unit_scale.real_units_per_sim_unit
        risk = runner.strategies.get(firm.id).risk_tolerance if firm.id in runner.strategies else 0.5
        damage = cfg.damage_probability * cfg.damage_share * unit_value * (1 + (1 - risk) * cfg.risk_aversion)
        own = shipped * (mean_km * cfg.own_rate * self.fuel_index + damage) + cfg.fleet_cost_per_day * 365
        rate = self.carriers.service_rate(firm) if self.carriers is not None else cfg.service_rate
        service = shipped * mean_km * rate * self.fuel_index
        choice = "service" if service < own else "own"
        if choice != firm.transport_mode:
            firm.transport_mode = choice
            state.events.append({"year": state.year, "day": runner.config.simulation.days_per_year,
                                 "firm": firm.id, "event": "transport_switch",
                                 "details": "jetzt Transportdienst" if choice == "service" else "jetzt eigene Flotte"})

    def _invest(self, runner, firm, summary, state, days) -> None:
        cfg = self.cfg
        env = runner.env
        runtime = env.runtimes[firm.id]
        if any(p[1] == firm.id for p in self.projects) or summary.profit <= 0:
            return
        capacity = env._effective_capacity(firm.id)
        unit_cost = cfg.build_cost_per_capacity_unit.get(firm.stage, 0.0) * runner.long_run.price_index
        utilization = summary.capacity_utilization if hasattr(summary, "capacity_utilization") else 0.0
        if utilization >= cfg.expand_utilization and capacity:
            units = max(1, round(capacity * cfg.expand_fraction))
            cost = units * unit_cost
            if runtime.cash >= cfg.cash_cover * cost:
                self._start(env, firm, "expand", units, cost, days, state)
                return
        if firm.stage == "retailer" and runtime.cash >= cfg.cash_cover * unit_cost * capacity * cfg.site_fraction:
            region = self._best_new_region(runner, firm)
            if region is not None:
                units = max(1, round(capacity * cfg.site_fraction))
                self._start(env, firm, "site", (region, units), units * unit_cost, days, state)

    def _start(self, env, firm, kind, payload, cost, days, state) -> None:
        if not env.can_spend(firm.id, cost):
            return
        cfg = self.cfg
        build = cfg.build_days.get(firm.stage, days)
        finish = env.period + build
        self.projects.append((finish, firm.id, kind, payload))
        daily = cost / (cfg.depreciation_years * days)
        self.depreciation.setdefault(firm.id, []).append((daily, finish + cfg.depreciation_years * days))
        what = f"+{payload} Kapazität" if kind == "expand" else f"Standort {payload[0]}"
        state.events.append({"year": state.year, "day": days, "firm": firm.id, "event": f"{kind}_started",
                             "details": f"{what}, Kosten {chf(cost)}, fertig in {build} Tagen"})

    def _finish_projects(self, runner, state) -> None:
        env = runner.env
        done = [p for p in self.projects if p[0] <= env.period]
        self.projects = [p for p in self.projects if p[0] > env.period]
        for _, firm_id, kind, payload in done:
            firm = runner.network.firm(firm_id)
            if not env.runtimes[firm_id].active:
                continue
            if kind == "expand":
                firm.machine_capacity += payload
                firm.capacity += payload
                self.stats["expansions"] += 1
            else:
                region, units = payload
                if region not in self.sites(firm):
                    firm.extra_regions.append(region)
                firm.machine_capacity += units
                firm.capacity += units
                self.stats["new_sites"] += 1
            state.events.append({"year": state.year, "day": runner.config.simulation.days_per_year,
                                 "firm": firm_id, "event": f"{kind}_finished",
                                 "details": f"+{payload} Kapazität" if kind == "expand"
                                 else f"Standort {payload[0]} (+{payload[1]} Kapazität)"})

    def catchment(self, retailers: list[Firm]) -> dict[str, float]:
        """Population a store reaches, each region weighted by 1 / (1 + km / travel_km); mean 1."""
        raw = {}
        for firm in retailers:
            reach = 0.0
            for region, share in self.population.items():
                place = self.regions[region]
                km = min(math.hypot(place.x - self.regions[s].x, place.y - self.regions[s].y)
                         * self.cfg.road_factor for s in self.sites(firm)) + self.cfg.local_km
                reach += share / (1 + km / self.cfg.travel_km)
            raw[firm.id] = reach
        mean = sum(raw.values()) / len(raw) if raw else 1.0
        return {k: v / mean for k, v in raw.items()}

    def retail_coverage(self, runner) -> dict[str, float]:
        """Retail capacity per population share in each region."""
        env = runner.env
        coverage = {name: 0.0 for name in self.regions}
        for firm in runner.network.firms_in("retailer"):
            if not env.runtimes[firm.id].active:
                continue
            sites = self.sites(firm)
            for region in sites:
                coverage[region] += env._effective_capacity(firm.id) / len(sites)
        return {name: coverage[name] / max(1e-9, self.population[name]) for name in coverage}

    def _best_new_region(self, runner, firm) -> str | None:
        coverage = self.retail_coverage(runner)
        options = [r for r in sorted(coverage) if r not in self.sites(firm)]
        if not options:
            return None
        region = min(options, key=lambda r: (coverage[r], r))
        mean = sum(coverage.values()) / len(coverage)
        return region if coverage[region] < self.cfg.site_coverage_gap * mean else None

    def entrant_region(self, runner, stage: str) -> str:
        """New firms settle where their stage has the least capacity per inhabitant."""
        env = runner.env
        load = {name: 0.0 for name in self.regions}
        for firm in runner.network.firms_in(stage):
            if env.runtimes[firm.id].active:
                load[firm.region] += env._effective_capacity(firm.id)
        return min(sorted(load), key=lambda r: load[r] / max(1e-9, self.population[r]))
