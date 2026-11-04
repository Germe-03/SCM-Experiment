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
    category: str = "beer"
    maturation_days: int = 0
    # Phase 4: quality bonus or malus of the vintage currently on sale (wine).
    vintage_bonus: float = 0.0


@dataclass
class ClassStats:
    demand: int = 0
    bought: int = 0
    spend: float = 0.0
    category_units: dict[str, int] = field(default_factory=dict)
    brand_units: dict[str, int] = field(default_factory=dict)


class BrandBook:
    """Brand state, factory production mix and the class-based consumer market."""

    def __init__(self, config: MarketConfig, firms: list[Firm]) -> None:
        if config.brands is None or config.consumers is None:
            raise ValueError("the market needs brands.yaml and consumers.yaml")
        self.config = config
        self.cfg = config.brands
        owners = {firm.id: firm for firm in firms}
        self.brands: dict[str, Brand] = {}
        for item in self.cfg.brands:
            owner = owners.get(item.owner)
            self.brands[item.id] = Brand(
                item.id, item.name, item.owner, item.positioning,
                owner.reputation if owner else 0.5, list(item.traits),
                item.category, item.maturation_days,
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
        # Phase 3: active trends as (trait, score boost, age groups; empty = all).
        self.trend_boosts: list[tuple[str, float, set[str]]] = []
        self.entrant_trait: str | None = None
        # Phase 4: categories with value factors and a fixed total need.
        cats = config.categories
        self.categories_on = cats.enabled and bool(cats.categories)
        self.cat_cfg = cats
        self.value = {c.name: c.value_factor for c in cats.categories} if self.categories_on else {}
        total_volume = sum(c.relative_volume for c in cats.categories) or 1.0
        self.base_share = {c.name: c.relative_volume / total_volume for c in cats.categories}
        self.global_weight = dict(self.base_share)
        self.retail_weight: dict[str, dict[str, float]] = {}
        self.export_units = 0
        # Phase 6: fear after a poisoning scandal lowers consumption of that category.
        self.fear: dict[str, float] = {}
        # Phase 10: awareness from marketing (0..1) per brand and per store.
        self.awareness: dict[str, float] = {}
        self.store_awareness: dict[str, float] = {}
        self.channel_units: dict[str, int] = {"store": 0, "restaurant": 0}
        self.channel_revenue: dict[str, float] = {"store": 0.0, "restaurant": 0.0}
        self.reset_year()

    # -- brand registry -------------------------------------------------
    def brands_of(self, owner_id: str) -> list[str]:
        return sorted(b.id for b in self.brands.values() if b.owner == owner_id)

    def add_brand_for(self, firm: Firm) -> str:
        """Give a new brewery its own brand, positioned by its archetype."""
        brand_id = f"{firm.id}_brand"
        positioning = self.cfg.entrant_positioning.get(firm.archetype, "standard")
        if firm.category == "beer":
            traits = list(self.cfg.entrant_traits.get(firm.archetype, ["lager"]))
        else:
            traits = [firm.category]
        trend_trait = getattr(self, "entrant_trait", None)
        categories = getattr(self, "value", {})
        if trend_trait and trend_trait not in traits and firm.category == "beer" and trend_trait not in categories:
            traits.append(trend_trait)
        maturation = 365 if firm.category == "wine" and not firm.importer else 0
        self.brands[brand_id] = Brand(brand_id, firm.name, firm.id, positioning, firm.reputation, traits,
                                      firm.category, maturation)
        if hasattr(self, "production_share"):
            self.production_share[brand_id] = 1.0
        return brand_id

    def quality(self, brand: Brand, env: MarketEnvironment) -> float:
        owner = env.runtimes.get(brand.owner)
        base = owner.quality_level if owner is not None else 0.5
        offset = self.cfg.quality_offsets.get(brand.positioning, 0.0) + brand.vintage_bonus
        return max(0.0, min(1.0, base + offset))

    def value_factor(self, brand_id: str) -> float:
        return self.value.get(self.brands[brand_id].category, 1.0) if self.value else 1.0

    def category_value(self, category: str) -> float:
        return self.value.get(category, 1.0) if self.value else 1.0

    def markup(self, firm: Firm) -> float:
        """Restaurants charge for service on top of the store price."""
        cfg = self.config.restaurants
        return cfg.markup if cfg.enabled and firm.channel == "restaurant" else 1.0

    def retail_price(self, sell_price: float, brand: Brand, firm: Firm | None = None) -> float:
        markup = self.markup(firm) if firm is not None else 1.0
        return sell_price * self.cfg.price_factors.get(brand.positioning, 1.0) * self.category_value(brand.category) * markup

    def out_of_home_share(self, cls) -> float:
        cfg = self.config.restaurants
        if not cfg.enabled:
            return 0.0
        share = cfg.out_of_home_share * cfg.age_factor.get(cls.age_group or "", 1.0)
        share *= 1 + cfg.income_step * ((cls.income_level or 3) - 3)
        return max(0.0, min(0.9, share))

    def parcel_value(self, parcel: dict[str, int], price: float) -> float:
        """Units of a mixed shipment times price, weighted by each brand's category."""
        return sum(units * price * self.value_factor(b) for b, units in parcel.items())

    # -- category weights ----------------------------------------------
    def class_shares(self, cls, boosts: dict[str, float]) -> dict[str, float]:
        """Category split of a class: base share, income tilt and trends (fixed total need)."""
        level = (cls.income_level or 3) - 3
        raw = {}
        for c in self.cat_cfg.categories:
            raw[c.name] = self.base_share[c.name] * c.income_tilt ** level * (1 + boosts.get(c.name, 0.0))
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}

    def customer_weights(self, firm: Firm) -> dict[str, float]:
        if firm.stage != "retailer":
            return self.global_weight
        own = self.retail_weight.get(firm.id, self.global_weight)
        bias = self.cat_cfg.retailer_bias.get(firm.archetype)
        if not bias:
            return own
        bw = self.cat_cfg.bias_weight
        return {c: (1 - bw) * own.get(c, 0.0) + bw * bias.get(c, 0.0) for c in self.base_share}

    def take_for(self, customer: Firm | None, stock: dict[str, int], quantity: int) -> dict[str, int]:
        """Ship from a mixed stock; the customer's category mix decides what it gets."""
        if not self.categories_on or customer is None:
            return take_from_stock(stock, quantity)
        weights = self.customer_weights(customer)
        by_cat: dict[str, int] = {}
        for b, units in stock.items():
            if units > 0:
                c = self.brands[b].category
                by_cat[c] = by_cat.get(c, 0) + units
        remaining = min(quantity, sum(by_cat.values()))
        alloc = {c: 0 for c in by_cat}
        while remaining > 0:
            open_cats = {c: max(1e-6, weights.get(c, 0.0)) for c in by_cat if alloc[c] < by_cat[c]}
            if not open_cats:
                break
            for c, units in largest_remainder(remaining, open_cats).items():
                units = min(units, by_cat[c] - alloc[c])
                alloc[c] += units
                remaining -= units
        parcel: dict[str, int] = {}
        for c, units in alloc.items():
            if units:
                sub = {b: v for b, v in stock.items() if v > 0 and self.brands[b].category == c}
                for b, got in take_from_stock(sub, units).items():
                    stock[b] -= got
                    parcel[b] = got
        return parcel

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
        # Units consumers asked for in the first round, also for empty shelves.
        self.brand_wanted: dict[str, int] = {b: 0 for b in self.brands}
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
                "positioning": brand.positioning, "category": brand.category, "owner_active": owner_active,
                "traits": list(brand.traits),
                "units_sold": self.brand_units.get(brand_id, 0),
                "revenue": self.brand_revenue.get(brand_id, 0.0),
                "market_share": self.brand_units.get(brand_id, 0) / total_units,
                "quality": quality, "reputation": brand.reputation,
                "awareness": self.awareness.get(brand_id, self.config.marketing.start_awareness),
            })
        floor_share = self.cfg.production_share_floor
        owners = {b.owner for b in self.brands.values()}
        # Breweries brew what consumers asked for, so trends reach production.
        for owner in owners:
            own = self.brands_of(owner)
            wanted = sum(self.brand_wanted.get(b, 0) for b in own)
            for b in own:
                share = self.brand_wanted.get(b, 0) / wanted if wanted else 1 / len(own)
                self.production_share[b] = max(floor_share, share)
        class_rows = [{
            "year": year, "consumer_class": name, "demand": stats.demand, "bought": stats.bought,
            "persons": self.classes[name].persons,
            "income_level": self.classes[name].income_level,
            "age_group": self.classes[name].age_group,
            "drinking_habit": name.rsplit("_", 1)[-1],
            "units_per_person": self.classes[name].units_per_person_per_year,
            "max_price": self.classes[name].max_price,
            "purchase_rate": stats.bought / stats.demand if stats.demand else 0.0,
            "category_shares": {c: stats.category_units.get(c, 0) / stats.bought if stats.bought else 0.0 for c in self.base_share or {"beer": 1}},
            "favourite_brand": max(sorted(stats.brand_units), key=stats.brand_units.get) if stats.brand_units else None,
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
        if self.fear:
            for name in demand_by_class:
                cls = self.classes[name]
                shares = self.class_shares(cls, {}) if self.categories_on else {"beer": 1.0}
                drop = sum(shares.get(c, 0.0) * f for c, f in self.fear.items())
                demand_by_class[name] = round(demand_by_class[name] * (1 - drop))
            total_demand = sum(demand_by_class.values())
        requested = {f.id: 0 for f in retailers}
        sold = {f.id: 0 for f in retailers}
        if not retailers:
            for name, units in demand_by_class.items():
                self.class_stats[name].demand += units
            return requested, sold, total_demand
        capacity = {f.id: env._effective_capacity(f.id) for f in retailers}
        geo = getattr(env, "geography", None)
        # Phase 5: a store's catchment (nearby population, falling with distance) scales its appeal.
        catchment = geo.catchment(retailers) if geo is not None else None
        restaurants = [f for f in retailers if f.channel == "restaurant"]
        stores = [f for f in retailers if f.channel != "restaurant"] or retailers
        home_demand = dict(demand_by_class)
        if restaurants and self.config.restaurants.enabled:
            # Phase 10: part of each class drinks out of home; unmet guests partly buy in stores.
            out = {n: round(u * self.out_of_home_share(self.classes[n])) for n, u in demand_by_class.items()}
            home_demand = {n: u - out[n] for n, u in demand_by_class.items()}
            bought_before = {n: self.class_stats[n].bought for n in out}
            reference = max(1.0, sum(out.values()) / len(restaurants))
            self._serve_group(env, restaurants, out, requested, sold, capacity, reference, catchment)
            spill = self.config.restaurants.spill_to_stores
            for n, units in out.items():
                missing = units - (self.class_stats[n].bought - bought_before[n])
                home_demand[n] += round(max(0, missing) * spill)
        reference = max(1.0, sum(home_demand.values()) / len(stores))
        self._serve_group(env, stores, home_demand, requested, sold, capacity, reference, catchment)
        for name, units in demand_by_class.items():
            self.class_stats[name].demand += units
        return requested, sold, max(0, total_demand - sum(sold.values()))

    def _serve_group(self, env, retailers, demand_by_class, requested, sold, capacity, reference,
                     catchment=None) -> None:
        """Serve the demand of one group of consumers from the given stores."""
        slope = self.config.consumers.wtp_slope
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
                price = env._market_price(self.retail_price(firm.sell_price, brand, firm))
                # Price score and willingness to pay compare the price per beer-equivalent
                # (restaurant guests accept the service markup).
                norm = price / (self.category_value(brand.category) * self.markup(firm))
                pairs[(firm.id, brand_id)] = (
                    norm, env._consumer_price_score(norm), quality[brand_id],
                    brand.reputation, firm.reputation, availability, price, brand.category,
                )
        # Trend multipliers per age group and brand, fixed for the day.
        trend_mult: dict[str | None, dict[str, float]] = {}
        if self.trend_boosts:
            for age in {self.classes[n].age_group for n in self.class_names}:
                trend_mult[age] = {
                    b: 1 + sum(boost for trait, boost, ages in self.trend_boosts
                               if trait in brand.traits and (not ages or age in ages))
                    for b, brand in self.brands.items()
                }
        # Phase 10: awareness from marketing, stronger for young classes.
        aware_mult: dict[str | None, tuple[dict[str, float], dict[str, float]]] = {}
        mk = self.config.marketing
        if mk.enabled:
            start = mk.start_awareness
            for age in {self.classes[n].age_group for n in self.class_names}:
                sens = mk.age_sensitivity.get(age or "", 1.0)
                aware_mult[age] = (
                    {b: 1 + sens * mk.brand_weight * (self.awareness.get(b, start) - 0.5) for b in self.brands},
                    {f.id: 1 + sens * mk.store_weight * (self.store_awareness.get(f.id, start) - 0.5) for f in retailers},
                )
        cat_boost: dict[str | None, dict[str, float]] = {}
        if self.categories_on:
            for age in {self.classes[n].age_group for n in self.class_names}:
                cat_boost[age] = {c: sum(boost for trait, boost, ages in self.trend_boosts
                                         if trait == c and (not ages or age in ages)) for c in self.base_share}
        class_cats = {n: self.class_shares(self.classes[n], cat_boost.get(self.classes[n].age_group, {}))
                      for n in self.class_names} if self.categories_on else {}
        sub = self.cat_cfg.substitution
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
                mult = trend_mult.get(cls.age_group)
                aware = aware_mult.get(cls.age_group)
                scores = {}
                for key, (price, p_score, q, brand_rep, store_rep, avail, _, cat) in pairs.items():
                    if price > cls.max_price * (1 + slope * (brand_rep - 0.5)):
                        continue
                    score = (w.price * p_score + w.quality * q + w.brand_reputation * brand_rep
                             + w.store_reputation * store_rep + w.availability * avail)
                    if mult:
                        score *= mult[key[1]]
                    if aware:
                        score *= aware[0][key[1]] * aware[1][key[0]]
                    scores[key] = score * catchment[key[0]] if catchment else score
                if not self.categories_on:
                    total_score = sum(scores.values())
                    if total_score > 0:
                        wants[name] = {key: units * value / total_score for key, value in scores.items()}
                    continue
                shares = class_cats[name]
                if round_index == 0:
                    # Fixed need per category; a category without any offer waits for the spill rounds.
                    by_cat: dict[str, float] = {}
                    for key, value in scores.items():
                        by_cat[pairs[key][7]] = by_cat.get(pairs[key][7], 0.0) + value
                    wants[name] = {key: units * shares[pairs[key][7]] * value / by_cat[pairs[key][7]]
                                   for key, value in scores.items() if by_cat[pairs[key][7]] > 0}
                else:
                    weighted = {key: value * (sub + (1 - sub) * shares[pairs[key][7]]) for key, value in scores.items()}
                    total_score = sum(weighted.values())
                    if total_score > 0:
                        wants[name] = {key: units * value / total_score for key, value in weighted.items()}
            pair_float: dict[tuple[str, str], float] = {}
            for shares in wants.values():
                for key, units in shares.items():
                    pair_float[key] = pair_float.get(key, 0.0) + units
            per_pair = largest_remainder(round(sum(pair_float.values())), pair_float)
            if round_index == 0:
                cat_total: dict[str, float] = {}
                cat_retail: dict[str, dict[str, float]] = {}
                for (firm_id, brand_id), units in per_pair.items():
                    requested[firm_id] += units
                    self.brand_wanted[brand_id] = self.brand_wanted.get(brand_id, 0) + units
                    c = self.brands[brand_id].category
                    cat_total[c] = cat_total.get(c, 0.0) + units
                    store = cat_retail.setdefault(firm_id, {})
                    store[c] = store.get(c, 0.0) + units
                if self.categories_on:
                    self._update_weights(cat_total, cat_retail)
            served = self._serve(env, per_pair, capacity, sold)
            for key, units in served.items():
                if not units:
                    continue
                takers = {name: shares[key] for name, shares in wants.items() if key in shares}
                for name, got in largest_remainder(units, takers).items():
                    got = min(got, unmet[name])
                    if got:
                        unmet[name] -= got
                        stats = self.class_stats[name]
                        brand_id = key[1]
                        category = self.brands[brand_id].category
                        stats.category_units[category] = stats.category_units.get(category, 0) + got
                        stats.brand_units[brand_id] = stats.brand_units.get(brand_id, 0) + got
                        self.class_stats[name].bought += got
                        self.class_stats[name].spend += got * pairs[key][6]
            pairs = {key: value for key, value in pairs.items()
                     if env.runtimes[key[0]].stock.get(key[1], 0) > 0 and sold[key[0]] < capacity[key[0]]}
            if not pairs or not any(unmet.values()):
                break

    def _update_weights(self, cat_total, cat_retail, alpha: float = 0.02) -> None:
        """Slowly follow what consumers ask for, market-wide and per store."""
        total = sum(cat_total.values())
        if total:
            self.global_weight = {c: (1 - alpha) * self.global_weight.get(c, 0.0) + alpha * cat_total.get(c, 0.0) / total
                                  for c in self.base_share}
        for firm_id, wanted in cat_retail.items():
            subtotal = sum(wanted.values())
            if not subtotal:
                continue
            old = self.retail_weight.get(firm_id, self.global_weight)
            self.retail_weight[firm_id] = {c: (1 - alpha) * old.get(c, 0.0) + alpha * wanted.get(c, 0.0) / subtotal
                                           for c in self.base_share}

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
            store = env.network.firm(firm_id)
            sell_price = store.sell_price
            restaurant = store.channel == "restaurant" and self.config.restaurants.enabled
            for key, units in limited.items():
                if not units:
                    continue
                brand = self.brands[key[1]]
                price = env._market_price(self.retail_price(sell_price, brand, store))
                runtime.stock[key[1]] -= units
                runtime.inventory -= units
                sold[firm_id] += units
                value = env._trade_value(units, price)
                runtime.revenue += value
                runtime.handling_cost += units * env.config.costs.handling_cost_per_unit * self.value_factor(key[1])
                if restaurant:
                    # Service, rent and kitchen grow with what the guests pay.
                    runtime.handling_cost += value * self.config.restaurants.service_cost_share
                channel = "restaurant" if restaurant else "store"
                self.channel_units[channel] += units
                self.channel_revenue[channel] += value
                self.brand_units[key[1]] = self.brand_units.get(key[1], 0) + units
                self.brand_revenue[key[1]] = self.brand_revenue.get(key[1], 0.0) + value
                served[key] = units
        return served
