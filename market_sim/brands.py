"""Phase 2: brands travelling through the chain and consumer classes buying them."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import TYPE_CHECKING

from market_sim.config import MarketConfig
from market_sim.models import Firm

if TYPE_CHECKING:
    from market_sim.environment import FirmRuntime, MarketEnvironment


def largest_remainder(total: int, weights: dict) -> dict:
    """Split ``total`` by non-negative weights; ties resolve by key order."""

    result = {key: 0 for key in weights}
    positive = {key: value for key, value in weights.items() if value > 0}
    weight_sum = sum(positive.values())
    total = max(0, int(total))
    if not total or weight_sum <= 0:
        return result
    quotas = {key: total * value / weight_sum for key, value in positive.items()}
    for key, quota in quotas.items():
        result[key] = floor(quota)
    remaining = total - sum(result.values())
    ranking = sorted(positive, key=lambda key: (-(quotas[key] - floor(quotas[key])), key))
    for key in ranking[:remaining]:
        result[key] += 1
    return result


def take_from_stock(stock: dict[str, int], quantity: int) -> dict[str, int]:
    """Remove ``quantity`` units from a brand stock in proportion to its mix."""

    taken = largest_remainder(min(quantity, sum(stock.values())), stock)
    for brand_id, units in taken.items():
        stock[brand_id] -= units
    return {brand_id: units for brand_id, units in taken.items() if units}


def add_to_stock(stock: dict[str, int], parcel: dict[str, int]) -> None:
    for brand_id, units in parcel.items():
        stock[brand_id] = stock.get(brand_id, 0) + units


@dataclass
class Brand:
    id: str
    name: str
    owner: str
    positioning: str
    reputation: float
    traits: list[str] = field(default_factory=list)


@dataclass
class ClassStats:
    demand: int = 0
    bought: int = 0
    spend: float = 0.0


class BrandBook:
    """Brand state, factory production mix and the class-based consumer market."""

    def __init__(self, config: MarketConfig, firms: list[Firm]) -> None:
        if config.brands is None or config.consumers is None:
            raise ValueError("consumer_model 'classes' needs brands.yaml and consumers.yaml")
        self.config = config
        self.cfg = config.brands
        owners = {firm.id: firm for firm in firms}
        self.brands: dict[str, Brand] = {}
        for item in self.cfg.brands:
            owner = owners.get(item.owner)
            self.brands[item.id] = Brand(
                item.id, item.name, item.owner, item.positioning,
                owner.reputation if owner else 0.5, list(item.traits),
            )
        for firm in firms:
            if firm.stage == "factory" and not self.brands_of(firm.id):
                self.add_brand_for(firm)
        self.production_share = {brand_id: 1.0 for brand_id in self.brands}
        units = config.unit_scale.real_units_per_sim_unit
        self.class_names = [c.name for c in config.consumers.classes]
        self.class_volume = {
            c.name: c.persons * c.units_per_person_per_year / units for c in config.consumers.classes
        }
        self.classes = {c.name: c for c in config.consumers.classes}
        self.reset_year()

    # -- brand registry -------------------------------------------------
    def brands_of(self, owner_id: str) -> list[str]:
        return sorted(b.id for b in self.brands.values() if b.owner == owner_id)

    def add_brand_for(self, firm: Firm) -> str:
        """Give a new brewery its own brand, positioned by its archetype."""
        brand_id = f"{firm.id}_brand"
        positioning = self.cfg.entrant_positioning.get(firm.archetype, "standard")
        self.brands[brand_id] = Brand(brand_id, firm.name, firm.id, positioning, firm.reputation, ["lager"])
        if hasattr(self, "production_share"):
            self.production_share[brand_id] = 1.0
        return brand_id

    def quality(self, brand: Brand, env: MarketEnvironment) -> float:
        owner = env.runtimes.get(brand.owner)
        base = owner.quality_level if owner is not None else 0.5
        return max(0.0, min(1.0, base + self.cfg.quality_offsets.get(brand.positioning, 0.0)))

    def retail_price(self, sell_price: float, brand: Brand) -> float:
        return sell_price * self.cfg.price_factors.get(brand.positioning, 1.0)

    # -- flows ----------------------------------------------------------
    def initial_stock(self, firm: Firm, inventory: int) -> dict[str, int]:
        if firm.stage == "factory":
            return self.production_mix(firm.id, inventory)
        return {k: v for k, v in largest_remainder(inventory, {b: 1.0 for b in sorted(self.brands)}).items() if v}

    def production_mix(self, factory_id: str, quantity: int) -> dict[str, int]:
        own = self.brands_of(factory_id)
        if not own:
            return {}
        mix = largest_remainder(quantity, {b: self.production_share.get(b, 1.0) for b in own})
        return {k: v for k, v in mix.items() if v}

    # -- yearly bookkeeping ---------------------------------------------
    def reset_year(self) -> None:
        self.brand_units: dict[str, int] = {b: 0 for b in self.brands}
        self.brand_revenue: dict[str, float] = {b: 0.0 for b in self.brands}
        self.class_stats: dict[str, ClassStats] = {name: ClassStats() for name in self.class_names}

    def year_end(self, env: MarketEnvironment, network, year: int) -> tuple[list[dict], list[dict]]:
        """Update reputations and production mix; return brand and class report rows."""
        total_units = sum(self.brand_units.values()) or 1
        brand_rows = []
        for brand_id in sorted(self.brands):
            brand = self.brands[brand_id]
            owner_active = brand.owner in env.runtimes and env.runtimes[brand.owner].active
            reliability = network.firm(brand.owner).reliability if brand.owner in env.runtimes else 0.5
            quality = self.quality(brand, env)
            target = self.cfg.quality_weight * quality + (1 - self.cfg.quality_weight) * reliability
            brand.reputation += self.cfg.reputation_speed * (target - brand.reputation)
            brand_rows.append({
                "year": year, "brand": brand_id, "name": brand.name, "owner": brand.owner,
                "positioning": brand.positioning, "owner_active": owner_active,
                "units_sold": self.brand_units.get(brand_id, 0),
                "revenue": self.brand_revenue.get(brand_id, 0.0),
                "market_share": self.brand_units.get(brand_id, 0) / total_units,
                "quality": quality, "reputation": brand.reputation,
            })
        floor_share = self.cfg.production_share_floor
        owners = {b.owner for b in self.brands.values()}
        for owner in owners:
            own = self.brands_of(owner)
            sold = sum(self.brand_units.get(b, 0) for b in own)
            for b in own:
                share = self.brand_units.get(b, 0) / sold if sold else 1 / len(own)
                self.production_share[b] = max(floor_share, share)
        class_rows = [{
            "year": year, "consumer_class": name, "demand": stats.demand, "bought": stats.bought,
            "no_purchase": stats.demand - stats.bought,
            "no_purchase_rate": (stats.demand - stats.bought) / stats.demand if stats.demand else 0.0,
            "avg_price_paid": stats.spend / stats.bought if stats.bought else 0.0,
        } for name, stats in self.class_stats.items()]
        self.reset_year()
        return brand_rows, class_rows

    def recall(self, owner_id: str, reputation_hit: float) -> None:
        for brand_id in self.brands_of(owner_id):
            brand = self.brands[brand_id]
            brand.reputation = max(0.0, brand.reputation - reputation_hit)

    # -- daily consumer market -----------------------------------------
    def fulfill(self, env: MarketEnvironment, total_demand: int) -> tuple[dict[str, int], dict[str, int], int]:
        """Serve one day of class demand; return requested and sold units per retailer and lost units."""
        retailers = sorted(
            (f for f in env.network.firms_in("retailer") if env.runtimes[f.id].active), key=lambda f: f.id
        )
        demand_by_class = largest_remainder(total_demand, self.class_volume)
        requested = {f.id: 0 for f in retailers}
        sold = {f.id: 0 for f in retailers}
        if not retailers:
            for name, units in demand_by_class.items():
                self.class_stats[name].demand += units
            return requested, sold, total_demand
        reference = max(1.0, total_demand / len(retailers))
        slope = self.config.consumers.wtp_slope
        capacity = {f.id: env._effective_capacity(f.id) for f in retailers}
        # Features per (retailer, brand): price, price score, quality, brand and store reputation, availability.
        pairs: dict[tuple[str, str], tuple] = {}
        quality = {b: self.quality(brand, env) for b, brand in self.brands.items()}
        # Empty shelves still attract a share in the first round, as in the old model;
        # otherwise an empty store would see no demand and never reorder.
        offered = [b for b, brand in sorted(self.brands.items())
                   if brand.owner in env.runtimes and env.runtimes[brand.owner].active]
        for firm in retailers:
            runtime = env.runtimes[firm.id]
            availability = env._consumer_availability_score(runtime.inventory, reference)
            carried = set(offered) | {b for b, units in runtime.stock.items() if units > 0}
            for brand_id in sorted(carried):
                brand = self.brands[brand_id]
                price = env._market_price(self.retail_price(firm.sell_price, brand))
                pairs[(firm.id, brand_id)] = (
                    price, env._consumer_price_score(price), quality[brand_id],
                    brand.reputation, firm.reputation, availability,
                )
        unmet = dict(demand_by_class)
        for round_index in range(4):
            # Fractional wants per class; small classes would otherwise always round
            # their few units onto the single best-scored store.
            wants: dict[str, dict[tuple[str, str], float]] = {}
            for name in self.class_names:
                units = unmet[name]
                if units <= 0:
                    continue
                cls = self.classes[name]
                w = cls.weights
                scores = {}
                for key, (price, p_score, q, brand_rep, store_rep, avail) in pairs.items():
                    if price > cls.max_price * (1 + slope * (brand_rep - 0.5)):
                        continue
                    scores[key] = (w.price * p_score + w.quality * q + w.brand_reputation * brand_rep
                                   + w.store_reputation * store_rep + w.availability * avail)
                total_score = sum(scores.values())
                if total_score > 0:
                    wants[name] = {key: units * value / total_score for key, value in scores.items()}
            pair_float: dict[tuple[str, str], float] = {}
            for shares in wants.values():
                for key, units in shares.items():
                    pair_float[key] = pair_float.get(key, 0.0) + units
            per_pair = largest_remainder(round(sum(pair_float.values())), pair_float)
            if round_index == 0:
                for (firm_id, _), units in per_pair.items():
                    requested[firm_id] += units
            served = self._serve(env, per_pair, capacity, sold)
            for key, units in served.items():
                if not units:
                    continue
                takers = {name: shares[key] for name, shares in wants.items() if key in shares}
                for name, got in largest_remainder(units, takers).items():
                    got = min(got, unmet[name])
                    if got:
                        unmet[name] -= got
                        self.class_stats[name].bought += got
                        self.class_stats[name].spend += got * pairs[key][0]
            pairs = {key: value for key, value in pairs.items()
                     if env.runtimes[key[0]].stock.get(key[1], 0) > 0 and sold[key[0]] < capacity[key[0]]}
            if not pairs or not any(unmet.values()):
                break
        for name, units in demand_by_class.items():
            self.class_stats[name].demand += units
        return requested, sold, max(0, total_demand - sum(sold.values()))

    def _serve(self, env, per_pair, capacity, sold) -> dict[tuple[str, str], int]:
        """Book sales limited by brand stock and remaining retailer capacity."""
        served: dict[tuple[str, str], int] = {}
        by_retailer: dict[str, dict[tuple[str, str], int]] = {}
        for key, units in per_pair.items():
            stock = env.runtimes[key[0]].stock.get(key[1], 0)
            by_retailer.setdefault(key[0], {})[key] = min(units, stock)
        for firm_id in sorted(by_retailer):
            limited = by_retailer[firm_id]
            room = max(0, capacity[firm_id] - sold[firm_id])
            if sum(limited.values()) > room:
                limited = largest_remainder(room, limited)
            runtime: FirmRuntime = env.runtimes[firm_id]
            sell_price = env.network.firm(firm_id).sell_price
            for key, units in limited.items():
                if not units:
                    continue
                brand = self.brands[key[1]]
                price = env._market_price(self.retail_price(sell_price, brand))
                runtime.stock[key[1]] -= units
                runtime.inventory -= units
                sold[firm_id] += units
                value = env._trade_value(units, price)
                runtime.revenue += value
                runtime.handling_cost += units * env.config.costs.handling_cost_per_unit
                self.brand_units[key[1]] = self.brand_units.get(key[1], 0) + units
                self.brand_revenue[key[1]] = self.brand_revenue.get(key[1], 0.0) + value
                served[key] = units
        return served
