"""Phase 29: private couriers and shippers' choice by total cost."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from market_sim.carriers import Carrier, CarrierMarket
from market_sim.kpi import REGION_DE, chf
from market_sim.models import Firm

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


NAMES = [
    "Blitz", "Velo", "Alpen", "Rhein", "Limmat", "Aare",
    "Gotthard", "Föhn", "Jura", "Rigi", "Pilatus", "Säntis",
]


def lerp(pair, t: float) -> float:
    """Interpolate a configured pair using a value in [0, 1]."""
    return pair[0] + (pair[1] - pair[0]) * t


class CourierMarket(CarrierMarket):
    """Private regional couriers competing with the Post for service shipments."""

    def __init__(self, config, geography, seed: int) -> None:
        super().__init__(config, geography, seed)
        self.config = config
        self.ccfg = config.carriers.couriers
        self.rng = random.Random(f"couriers-{seed}")
        self.couriers: dict[str, Carrier] = {}
        self.courier_info: dict[str, dict] = {}
        self.assignment: dict[tuple[str, str], str] = {}
        self.experience: dict[tuple[str, str], list[float]] = {}
        self.learned: dict[tuple[str, str], float] = {}
        self.region_carrier_km: dict[tuple[str, str], float] = {}
        self.region_carrier_rev: dict[tuple[str, str], float] = {}
        self._counter = 0
        self.mean_share = (
            1 / len(geography.population) if geography.population else 0.0
        )

    def carriers(self) -> list[Carrier]:
        return [self.post] + [
            courier for courier in self.couriers.values() if courier.active
        ]

    def carrier_for(self, supplier: Firm, customer: Firm) -> Carrier:
        cid = self.assignment.get((supplier.id, customer.region))
        courier = self.couriers.get(cid) if cid is not None else None
        if (
            courier is not None
            and courier.active
            and customer.region in courier.regions
        ):
            return courier
        return self.post

    def rate(self, supplier: Firm, customer: Firm) -> float:
        carrier = self.carrier_for(supplier, customer)
        if carrier is self.post:
            return self.post.tariff
        return self.courier_info[carrier.id]["price"][customer.region]

    def damage_probability(self, supplier: Firm, customer: Firm) -> float:
        carrier = self.carrier_for(supplier, customer)
        if carrier is self.post:
            return 0.0
        return self.courier_info[carrier.id]["damage"]

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
        delay = super().book(
            period, supplier, customer, units, km, cost, fuel_index
        )
        if carrier is not self.post:
            info = self.courier_info[carrier.id]
            if self.rng.random() < info["delay"]:
                delay += self.ccfg.delay_days
                if delay == self.ccfg.delay_days:
                    carrier.delayed_units += units
                carrier.delay_unit_days += units * self.ccfg.delay_days

        experience = self.experience.setdefault(
            (supplier.id, carrier.id), [0.0, 0.0]
        )
        experience[0] += units
        experience[1] += units * delay

        region = customer.region
        key = (carrier.id, region)
        self.region_carrier_km[key] = (
            self.region_carrier_km.get(key, 0.0) + units * km
        )
        self.region_carrier_rev[key] = (
            self.region_carrier_rev.get(key, 0.0) + cost
        )
        return delay

    def service_rate(self, firm: Firm) -> float:
        prices = []
        for (firm_id, region), cid in sorted(self.assignment.items()):
            if firm_id != firm.id:
                continue
            if cid == self.post.id:
                prices.append(self.post.tariff)
                continue
            courier = self.couriers.get(cid)
            if (
                courier is not None
                and courier.active
                and region in courier.regions
            ):
                prices.append(self.courier_info[cid]["price"][region])
        return sum(prices) / len(prices) if prices else self.post.tariff

    def region_cost(self, region: str, runner, unit_km: float) -> float:
        population_share = self.geography.population[region]
        fuel = self.geography.fuel_index
        price_index = runner.long_run.price_index
        density = (
            (self.mean_share / population_share) ** self.ccfg.density_exponent
            if population_share > 0
            else 0.0
        )
        return (
            self.ccfg.variable_rate * density * fuel
            + self.ccfg.fixed_cost_per_day_per_region
            * self.days_per_year
            * price_index
            / max(1.0, self.ccfg.expected_share * unit_km)
        )

    def margin(self, region: str, runner, unit_km: float) -> float:
        cost = self.region_cost(region, runner, unit_km)
        if cost == 0:
            return float("inf")
        return self.post.tariff * self.geography.fuel_index / cost - 1

    def unit_value(self, firm: Firm) -> float:
        return (
            self.config.stage_prices[firm.stage].base
            * self.config.unit_scale.real_units_per_sim_unit
        )

    @staticmethod
    def risk(runner, firm: Firm) -> float:
        return (
            runner.strategies[firm.id].risk_tolerance
            if firm.id in runner.strategies
            else 0.5
        )

    def _event(
        self, state: RunState, firm: str, event: str, details: str
    ) -> None:
        state.events.append({
            "year": state.year,
            "day": self.days_per_year,
            "firm": firm,
            "event": event,
            "details": details,
        })

    def _set_capacity(self, courier: Carrier) -> None:
        courier.capacity_per_day = (
            self.ccfg.capacity_per_region * len(courier.regions)
        )

    def _new_courier(
        self,
        region: str,
        risk: float,
        damage: float,
        delay: float,
        cash: float,
        founded: int,
    ) -> Carrier:
        self._counter += 1
        n = self._counter
        name = f"{NAMES[(n - 1) % len(NAMES)]} Kurier"
        if n > len(NAMES):
            name += f" {n}"
        cid = f"kurier_{n:02d}"
        courier = Carrier(
            id=cid,
            name=name,
            kind="courier",
            tariff=0.0,
            capacity_per_day=self.ccfg.capacity_per_region,
            cash=cash,
            regions=[region],
        )
        self.couriers[cid] = courier
        self.courier_info[cid] = {
            "risk": risk,
            "damage": damage,
            "delay": delay,
            "price": {region: 0.0},
            "loss_years": {region: 0},
            "debt_interest": 0.0,
            "founded": founded,
        }
        return courier

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        region_km = dict(self.region_unit_km)
        courier_region_km = dict(self.region_carrier_km)
        courier_region_rev = dict(self.region_carrier_rev)
        price_index = runner.long_run.price_index
        policy_rate = getattr(
            getattr(runner.env, "central_bank", None), "policy_rate", 0.0
        )

        profits: dict[str, float] = {}
        revenues: dict[str, float] = {}
        courier_rows: list[dict] = []

        for cid, courier in self.couriers.items():
            if not courier.active:
                continue
            info = self.courier_info[cid]
            variable = self.ccfg.variable_rate * courier.fuel_km
            fixed = (
                self.ccfg.fixed_cost_per_day_per_region
                * courier.days
                * len(courier.regions)
                * price_index
            )
            interest = max(0.0, -courier.cash) * (
                policy_rate + self.ccfg.interest_spread
            )
            info["debt_interest"] = interest
            profit = courier.revenue - variable - fixed - interest
            courier.cash += profit
            profits[cid] = profit
            revenues[cid] = courier.revenue

            fixed_per_region = (
                self.ccfg.fixed_cost_per_day_per_region
                * courier.days
                * price_index
            )
            for region in sorted(courier.regions):
                region_key = (cid, region)
                region_profit = (
                    courier_region_rev.get(region_key, 0.0)
                    - self.ccfg.variable_rate
                    * courier_region_km.get(region_key, 0.0)
                    * self.geography.fuel_index
                    - fixed_per_region
                )
                info["loss_years"][region] = (
                    info["loss_years"].get(region, 0) + 1
                    if region_profit < 0
                    else 0
                )

            utilization = (
                (courier.load_days / courier.days) / courier.capacity_per_day
                if courier.capacity_per_day > 0 and courier.days > 0
                else 0.0
            )
            mean_price = (
                sum(info["price"][region] for region in courier.regions)
                / len(courier.regions)
                if courier.regions
                else 0.0
            )
            courier_rows.append({
                "year": state.year,
                "carrier": courier.id,
                "name": courier.name,
                "kind": courier.kind,
                "tariff": round(mean_price, 4),
                "next_tariff": round(mean_price, 4),
                "units": courier.units,
                "unit_km": round(courier.unit_km, 1),
                "revenue": round(courier.revenue, 2),
                "variable_cost": round(variable, 2),
                "fixed_cost": round(fixed, 2),
                "profit": round(profit, 2),
                "bundesbeitrag": 0.0,
                "cash": round(courier.cash, 2),
                "capacity_per_day": round(courier.capacity_per_day, 1),
                "utilization": round(utilization, 4),
                "busy_days": courier.busy_days,
                "delayed_units": courier.delayed_units,
                "mean_delay_days": (
                    round(courier.delay_unit_days / courier.units, 4)
                    if courier.units
                    else 0.0
                ),
                "regions": ";".join(courier.regions),
                "held_units": self.held_units(),
                "risk": info["risk"],
                "damage_probability": info["damage"],
                "delay_probability": info["delay"],
            })

        self.learned = {
            key: delay / units
            for key, (units, delay) in self.experience.items()
            if units > 0
        }
        self.experience.clear()

        super().year_end(runner, state)
        post_row = self.reports[-1]
        for row in courier_rows:
            row["share_own"] = post_row["share_own"]
            row["share_post"] = post_row["share_post"]
            row["share_couriers"] = post_row["share_couriers"]
        self.reports.extend(courier_rows)

        for cid in sorted(self.couriers):
            courier = self.couriers[cid]
            if courier.active and courier.cash < -self.ccfg.credit_limit:
                courier.active = False
                self._event(
                    state,
                    cid,
                    "courier_bankrupt",
                    f"{courier.name} ist pleite (Kasse {chf(courier.cash)})",
                )
                self.assignment = {
                    key: value for key, value in self.assignment.items()
                    if value != cid
                }

        for cid in sorted(self.couriers):
            target = self.couriers[cid]
            if not target.active or profits.get(cid, 0.0) >= 0:
                continue
            if self.rng.random() >= self.ccfg.takeover_probability:
                continue
            buyers = [
                courier for other_id, courier in self.couriers.items()
                if other_id != cid
                and courier.active
                and courier.cash > max(0.0, target.cash) + 0.5 * revenues[cid]
            ]
            if not buyers:
                continue
            buyer = min(buyers, key=lambda courier: (-courier.cash, courier.id))
            union = sorted(set(buyer.regions) | set(target.regions))
            blocked = False
            for region in union:
                total_km = region_km.get(region, 0.0)
                combined_km = (
                    courier_region_km.get((buyer.id, region), 0.0)
                    + courier_region_km.get((target.id, region), 0.0)
                )
                share = combined_km / total_km if total_km > 0 else 0.0
                if share > self.ccfg.max_region_share:
                    blocked = True
                    break
            if blocked:
                self._event(
                    state,
                    cid,
                    "courier_takeover_blocked",
                    f"Wettbewerbsbehörde verbietet Übernahme von "
                    f"{target.name} durch {buyer.name}",
                )
                continue

            old_regions = set(buyer.regions)
            buyer.regions = union
            buyer.cash += target.cash
            buyer_info = self.courier_info[buyer.id]
            target_info = self.courier_info[target.id]
            for region in sorted(set(target.regions) - old_regions):
                buyer_info["price"][region] = target_info["price"][region]
                buyer_info["loss_years"][region] = target_info["loss_years"].get(
                    region, 0
                )
            self._set_capacity(buyer)
            target.active = False
            self.assignment = {
                key: (buyer.id if value == cid else value)
                for key, value in self.assignment.items()
            }
            self._event(
                state,
                cid,
                "courier_takeover",
                f"{buyer.name} übernimmt {target.name}",
            )

        for cid in sorted(self.couriers):
            courier = self.couriers[cid]
            if not courier.active:
                continue
            info = self.courier_info[cid]
            dropped = [
                region for region in sorted(courier.regions)
                if info["loss_years"].get(region, 0)
                >= self.ccfg.abandon_after_years
            ]
            if len(dropped) < len(courier.regions):
                for region in dropped:
                    courier.regions.remove(region)
                    info["price"].pop(region, None)
                    info["loss_years"].pop(region, None)
                    self.assignment = {
                        key: value
                        for key, value in self.assignment.items()
                        if not (value == cid and key[1] == region)
                    }
                    self._event(
                        state,
                        cid,
                        "courier_region_closed",
                        f"{courier.name} schliesst "
                        f"{REGION_DE.get(region, region)}",
                    )
                self._set_capacity(courier)

            if (
                profits.get(cid, 0.0) > 0
                and courier.cash
                > self.ccfg.fixed_cost_per_day_per_region
                * self.days_per_year
                * price_index
            ):
                if self.rng.random() < self.ccfg.expand_probability:
                    options = [
                        region for region in sorted(self.geography.population)
                        if region not in courier.regions
                    ]
                    if options:
                        region = max(
                            options,
                            key=lambda candidate: (
                                self.margin(
                                    candidate,
                                    runner,
                                    region_km.get(candidate, 0.0),
                                ),
                                candidate,
                            ),
                        )
                        if (
                            self.margin(
                                region, runner, region_km.get(region, 0.0)
                            )
                            >= self.ccfg.min_margin
                        ):
                            courier.regions.append(region)
                            courier.regions.sort()
                            info["price"][region] = 0.0
                            info["loss_years"][region] = 0
                            self._set_capacity(courier)
                            self._event(
                                state,
                                cid,
                                "courier_region_opened",
                                f"{courier.name} eröffnet "
                                f"in {REGION_DE.get(region, region)}",
                            )

        margins = {
            region: self.margin(region, runner, region_km.get(region, 0.0))
            for region in sorted(self.geography.population)
        }
        eligible = {
            region: margin for region, margin in margins.items()
            if margin >= self.ccfg.min_margin
        }
        max_margin = max(eligible.values(), default=0.0)
        draws = {
            region: self.rng.random()
            for region in sorted(self.geography.population)
        }
        selected = []
        for region in sorted(self.geography.population):
            if region not in eligible or max_margin <= 0:
                continue
            chance = (
                self.ccfg.entry_probability
                * eligible[region]
                / max_margin
            )
            if draws[region] < chance:
                selected.append(region)
        selected.sort(key=lambda region: (-eligible[region], region))

        for region in selected[:self.ccfg.max_entries_per_year]:
            risk = self.rng.random()
            courier = self._new_courier(
                region,
                risk,
                lerp(self.ccfg.damage_probability, risk),
                lerp(self.ccfg.delay_probability, risk),
                self.ccfg.start_cash * price_index,
                state.year,
            )
            self._event(
                state,
                courier.id,
                "courier_entry",
                f"{courier.name} startet in "
                f"{REGION_DE.get(region, region)}",
            )

        for cid, courier in self.couriers.items():
            if not courier.active:
                continue
            info = self.courier_info[cid]
            for region in sorted(courier.regions):
                cost = self.region_cost(
                    region, runner, region_km.get(region, 0.0)
                )
                undercut = lerp(self.ccfg.undercut, info["risk"])
                info["price"][region] = max(
                    cost * (1 + self.ccfg.min_markup)
                    / self.geography.fuel_index,
                    self.post.tariff * (1 - undercut),
                )
            self._set_capacity(courier)

        env = runner.env
        active_firms = {
            firm.id: firm for firm in runner._firms()
            if env.runtimes[firm.id].active
        }
        for key in list(self.assignment):
            firm = active_firms.get(key[0])
            if firm is None or firm.transport_mode != "service":
                del self.assignment[key]

        switching_cost_share = self.config.carriers.switching_cost_share
        for firm in sorted(active_firms.values(), key=lambda item: item.id):
            if firm.transport_mode != "service" or firm.stage == "retailer":
                continue
            downstream_stage = runner.network.downstream_stage(firm.stage)
            customers = [
                customer for customer in active_firms.values()
                if customer.stage == downstream_stage
            ]
            by_region: dict[str, list[Firm]] = {}
            for customer in customers:
                by_region.setdefault(customer.region, []).append(customer)

            risk = self.risk(runner, firm)
            value = self.unit_value(firm)
            penalty_factor = (
                1 + (1 - risk) * self.config.geography.risk_aversion
            )
            for region in sorted(by_region):
                region_customers = sorted(
                    by_region[region], key=lambda customer: customer.id
                )
                mean_km = sum(
                    self.geography.km(firm, customer)
                    for customer in region_customers
                ) / len(region_customers)
                options = [self.post]
                options.extend(
                    courier for courier in self.couriers.values()
                    if courier.active and region in courier.regions
                )
                options.sort(key=lambda carrier: carrier.id)
                current = self.assignment.get((firm.id, region), self.post.id)

                def total_cost(carrier: Carrier) -> float:
                    if carrier is self.post:
                        price = self.post.tariff
                        damage = 0.0
                    else:
                        info = self.courier_info[carrier.id]
                        price = info["price"][region]
                        damage = info["damage"]
                    return (
                        price * mean_km * self.geography.fuel_index
                        + damage
                        * self.config.geography.damage_share
                        * value
                        * penalty_factor
                        + self.learned.get((firm.id, carrier.id), 0.0)
                        * self.config.carriers.delay_cost_per_unit_day
                        * penalty_factor
                        + (
                            # Switching costs a share of the yearly transport bill per unit.
                            switching_cost_share * price * mean_km * self.geography.fuel_index
                            if carrier.id != current
                            else 0.0
                        )
                    )

                chosen = min(
                    options,
                    key=lambda carrier: (
                        total_cost(carrier),
                        0 if carrier.id == current else 1,
                        0 if carrier is self.post else 1,
                    ),
                )
                if chosen.id != current:
                    self._event(
                        state,
                        firm.id,
                        "carrier_switch",
                        f"Transport nach {REGION_DE.get(region, region)} "
                        f"jetzt mit {chosen.name}",
                    )
                self.assignment[(firm.id, region)] = chosen.id

        self.region_carrier_km = {}
        self.region_carrier_rev = {}

    def stats(self) -> dict[str, float]:
        result = super().stats()
        result["active_couriers"] = sum(
            courier.active for courier in self.couriers.values()
        )
        return result
