"""Phase 28: the Post as a transport actor.

Fixed costs follow the smoothed volume with delay, and the tariff moves halfway
to the long-run average cost, max 5 % per year.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from market_sim.kpi import chf
from market_sim.models import Firm

if TYPE_CHECKING:
    from market_sim.environment import MarketEnvironment
    from market_sim.runner import RunState, SimulationRunner


@dataclass
class Carrier:
    id: str
    name: str
    kind: str
    tariff: float
    capacity_per_day: float
    cash: float = 0.0
    active: bool = True
    regions: list[str] = field(default_factory=list)
    # Queue state.
    today_load: float = 0.0
    waiting_units: float = 0.0
    # Yearly accumulators.
    units: int = 0
    unit_km: float = 0.0
    fuel_km: float = 0.0
    revenue: float = 0.0
    delayed_units: int = 0
    delay_unit_days: float = 0.0
    busy_days: int = 0
    load_days: float = 0.0
    days: int = 0
    pending_capacity: list[tuple[int, float]] = field(default_factory=list)

    def reset_year(self) -> None:
        self.units = 0
        self.unit_km = 0.0
        self.fuel_km = 0.0
        self.revenue = 0.0
        self.delayed_units = 0
        self.delay_unit_days = 0.0
        self.busy_days = 0
        self.load_days = 0.0
        self.days = 0


class CarrierMarket:
    """Deterministic transport market operated by the Post."""

    def __init__(self, config, geography, seed: int) -> None:
        self.cfg = config.carriers
        self.geography = geography
        self.days_per_year = config.simulation.days_per_year
        self.post = Carrier(
            id="post",
            name="Die Post",
            kind="post",
            tariff=self.cfg.post.start_rate,
            capacity_per_day=self.cfg.post.capacity_per_day,
            regions=sorted(geography.regions),
        )
        self.start_capacity = self.cfg.post.capacity_per_day
        self.network_per_day = float(self.cfg.post.fixed_cost_per_day)
        self.smoothed_fuel_km: float | None = None
        self.fixed_rate = max(
            0.0,
            self.cfg.post.start_rate / (1 + self.cfg.post.margin)
            - self.cfg.post.variable_rate,
        )
        self.held: list[tuple[int, str, dict[str, int], int]] = []
        self.own_units = 0
        self.own_unit_km = 0.0
        self.region_unit_km: dict[str, float] = {
            region: 0.0 for region in geography.regions
        }
        self.bundesbeitrag_total = 0.0
        # Phase 54: profits of the Post are kept; losses are paid from here before the Bund helps.
        self.reserve = 0.0
        # Share of tariff x fuel-km the Post really bills (transport-efficiency projects lower it).
        self.realization = 1.0
        self.reports: list[dict] = []
        self.lost_units = 0

    def carriers(self) -> list[Carrier]:
        return [self.post]

    def carrier_for(self, supplier: Firm, customer: Firm) -> Carrier:
        return self.post

    def rate(self, supplier: Firm, customer: Firm) -> float:
        return self.carrier_for(supplier, customer).tariff

    def service_locked(self, firm_id: str, year: int) -> bool:
        """Phase 54: no contracts without couriers."""
        return False

    def service_rate(self, firm: Firm) -> float:
        return self.post.tariff

    def damage_probability(self, supplier: Firm, customer: Firm) -> float:
        return 0.0

    def book(
        self,
        period: int,
        supplier: Firm,
        customer: Firm,
        units: int,
        km: float,
        cost: float,
        fuel_index: float,
    ) -> int:
        carrier = self.carrier_for(supplier, customer)
        distance = units * km
        carrier.units += units
        carrier.unit_km += distance
        carrier.fuel_km += distance * fuel_index
        carrier.revenue += cost
        region = customer.region
        self.region_unit_km[region] = self.region_unit_km.get(region, 0.0) + distance

        delay = 0
        if carrier.capacity_per_day > 0:
            position = carrier.waiting_units + carrier.today_load
            delay = int((position + units - 1) // carrier.capacity_per_day)
        carrier.today_load += units
        if delay > 0:
            carrier.delayed_units += units
            carrier.delay_unit_days += units * delay
        return delay

    def record_own(self, customer: Firm, units: int, km: float) -> None:
        distance = units * km
        self.own_units += units
        self.own_unit_km += distance
        region = customer.region
        self.region_unit_km[region] = self.region_unit_km.get(region, 0.0) + distance

    def hold(
        self, release_period: int, customer_id: str, parcel: dict[str, int], units: int
    ) -> None:
        self.held.append((release_period, customer_id, parcel, units))

    def release(self, env: MarketEnvironment) -> None:
        remaining = []
        for release_period, customer_id, parcel, units in self.held:
            if release_period > env.period:
                remaining.append((release_period, customer_id, parcel, units))
                continue
            runtime = env.runtimes.get(customer_id)
            if runtime is None or not runtime.active:
                self.lost_units += units
                continue
            incoming = runtime.incoming_brands[-1]
            for brand, count in parcel.items():
                incoming[brand] = incoming.get(brand, 0) + count
            runtime.incoming_shipments[-1] += units
        self.held = remaining

    def held_units(self) -> int:
        return sum(units for _, _, _, units in self.held)

    def daily(self, env: MarketEnvironment) -> None:
        for carrier in self.carriers():
            carrier.days += 1
            carrier.load_days += carrier.today_load
            if carrier.capacity_per_day > 0:
                if carrier.waiting_units + carrier.today_load > carrier.capacity_per_day:
                    carrier.busy_days += 1
                carrier.waiting_units = max(
                    0.0,
                    carrier.waiting_units + carrier.today_load - carrier.capacity_per_day,
                )
            else:
                carrier.waiting_units = 0.0
            carrier.today_load = 0.0

            ready = [
                (period, capacity)
                for period, capacity in carrier.pending_capacity
                if period <= env.period
            ]
            carrier.pending_capacity = [
                (period, capacity)
                for period, capacity in carrier.pending_capacity
                if period > env.period
            ]
            for _, capacity in ready:
                carrier.capacity_per_day = capacity

    def fixed_cost_year(self, runner: SimulationRunner) -> float:
        return (
            self.network_per_day
            * self.post.days
            * runner.long_run.price_index
        )

    def variable_cost_rate(self, price_index: float) -> float:
        """Variable cost per unit-km of the Post; follows the price index (Phase 54)."""
        rate = self.cfg.post.variable_rate
        return rate * price_index if self.cfg.post.variable_follows_inflation else rate

    def adapt_network(self, price_index: float) -> None:
        fuel_km = self.post.fuel_km
        floor = self.cfg.post.fixed_cost_per_day
        first_volume_year = self.smoothed_fuel_km is None

        # Once the Post has carried anything, empty years also lower the smoothed
        # volume, so the network shrinks instead of being paid by the Bund for ever.
        if fuel_km > 0 or self.smoothed_fuel_km is not None:
            if self.smoothed_fuel_km is None:
                self.smoothed_fuel_km = fuel_km
            else:
                self.smoothed_fuel_km += self.cfg.post.volume_smoothing * (
                    fuel_km - self.smoothed_fuel_km
                )

        if self.smoothed_fuel_km is None:
            return

        target = max(
            floor,
            self.fixed_rate
            * self.smoothed_fuel_km
            / self.days_per_year
            / max(price_index, 1e-9),
        )
        if first_volume_year:
            self.network_per_day = target
        else:
            self.network_per_day += self.cfg.post.network_adjust * (
                target - self.network_per_day
            )
        self.network_per_day = max(floor, self.network_per_day)

        if first_volume_year and self.post.capacity_per_day > 0:
            mean_load = (
                self.post.load_days / self.post.days if self.post.days else 0
            )
            if not self.post.pending_capacity:
                self.post.capacity_per_day = max(
                    self.post.capacity_per_day, mean_load * 1.5
                )

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        year = state.year
        post = self.post
        fixed = self.fixed_cost_year(runner)
        variable = self.variable_cost_rate(runner.long_run.price_index) * post.fuel_km
        profit = post.revenue - fixed - variable
        if self.cfg.post.reserve_enabled:
            covered = min(self.reserve, max(0.0, -profit))
            self.reserve = max(0.0, self.reserve + profit)
            bundesbeitrag = max(0.0, -profit - covered)
            post.cash = self.reserve
        else:
            bundesbeitrag = max(0.0, -profit)
            post.cash += profit + bundesbeitrag
        self.bundesbeitrag_total += bundesbeitrag
        if bundesbeitrag > 0:
            state.events.append({
                "year": year,
                "day": self.days_per_year,
                "firm": "post",
                "event": "bundesbeitrag",
                "details": f"Bund deckt Verlust der Post: {chf(bundesbeitrag)}",
            })

        utilization = (
            (post.load_days / post.days) / post.capacity_per_day
            if post.capacity_per_day > 0 and post.days > 0
            else 0.0
        )
        if (
            post.capacity_per_day > 0
            and utilization >= self.cfg.post.expand_utilization
            and not post.pending_capacity
        ):
            old_capacity = post.capacity_per_day
            new_capacity = old_capacity * (1 + self.cfg.post.expand_step)
            ready = runner.env.period + self.cfg.post.expansion_delay_days
            post.pending_capacity.append((ready, new_capacity))
            state.events.append({
                "year": year,
                "day": self.days_per_year,
                "firm": "post",
                "event": "post_capacity",
                "details": (
                    f"Post baut aus: {old_capacity:.0f} -> {new_capacity:.0f} "
                    f"Einheiten pro Tag ab Tag {ready}"
                ),
            })

        self.adapt_network(runner.long_run.price_index)

        old = post.tariff
        if self.cfg.post.revenue_realization and post.fuel_km > 0 and old > 0:
            raw = min(1.0, max(0.3, post.revenue / (old * post.fuel_km)))
            self.realization += self.cfg.post.realization_smoothing * (raw - self.realization)
        # Cost-covering on the volume expected next year: the smoothed one, but not above last year's.
        expected = self.smoothed_fuel_km
        if expected is not None and self.cfg.post.expect_min_of_last and post.fuel_km > 0:
            expected = min(expected, post.fuel_km)
        if expected is not None and expected > 0:
            next_fixed = (
                self.network_per_day
                * self.days_per_year
                * runner.long_run.price_index
            )
            # Cost-covering on the expected (smoothed) volume; the reserve gap is closed slowly.
            reserve_gap = 0.0
            if self.cfg.post.reserve_enabled:
                reserve_gap = self.cfg.post.reserve_adjust * (
                    self.cfg.post.reserve_target_years * next_fixed - self.reserve
                )
            target = max(0.0, (
                self.variable_cost_rate(runner.long_run.price_index)
                + (next_fixed + reserve_gap) / expected
            ) * (1 + self.cfg.post.margin) / max(0.3, self.realization))
            desired = old + self.cfg.post.tariff_adjust * (target - old)
            step = self.cfg.post.max_tariff_step
            post.tariff = min(old * (1 + step), max(old * (1 - step), desired))
        if post.tariff != old:
            state.events.append({
                "year": year,
                "day": self.days_per_year,
                "firm": "post",
                "event": "post_tariff",
                "details": f"Posttarif {old:.3f} -> {post.tariff:.3f} CHF pro Einheit und km",
            })

        total = self.own_unit_km + sum(c.unit_km for c in self.carriers())
        share_own = self.own_unit_km / total if total else 0.0
        share_post = post.unit_km / total if total else 0.0
        share_couriers = max(0.0, 1 - share_own - share_post) if total else 0.0
        self.reports.append({
            "year": year,
            "carrier": post.id,
            "name": post.name,
            "kind": post.kind,
            "tariff": round(old, 4),
            "next_tariff": round(post.tariff, 4),
            "units": post.units,
            "unit_km": round(post.unit_km, 1),
            "revenue": round(post.revenue, 2),
            "variable_cost": round(variable, 2),
            "fixed_cost": round(fixed, 2),
            "profit": round(profit, 2),
            "bundesbeitrag": round(bundesbeitrag, 2),
            "cash": round(post.cash, 2),
            "reserve": round(self.reserve, 2),
            "realization": round(self.realization, 4),
            "capacity_per_day": round(post.capacity_per_day, 1),
            "utilization": round(utilization, 4),
            "busy_days": post.busy_days,
            "delayed_units": post.delayed_units,
            "mean_delay_days": round(post.delay_unit_days / post.units, 4) if post.units else 0.0,
            "regions": ";".join(post.regions),
            "share_own": round(share_own, 4),
            "share_post": round(share_post, 4),
            "share_couriers": round(share_couriers, 4),
            "held_units": self.held_units(),
            "network_per_day": round(self.network_per_day, 1),
            "smoothed_fuel_km": round(self.smoothed_fuel_km, 1) if self.smoothed_fuel_km is not None else 0.0,
        })

        for carrier in self.carriers():
            carrier.reset_year()
        self.own_units = 0
        self.own_unit_km = 0.0
        self.region_unit_km = {region: 0.0 for region in self.region_unit_km}

    def stats(self) -> dict[str, float]:
        if not self.reports:
            return {}
        report = self.reports[-1]
        return {
            "post_tariff": report["next_tariff"],
            "bundesbeitrag": report["bundesbeitrag"],
            "post_share": report["share_post"],
            "courier_share": report["share_couriers"],
            "own_fleet_share": report["share_own"],
            "mean_delay_days": report["mean_delay_days"],
        }
