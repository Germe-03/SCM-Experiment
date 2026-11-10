"""Phase 17: listed firms, share prices and a chain-linked stock index."""

from __future__ import annotations

import math
import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class StockMarket:
    """Daily share prices and a chain-linked stock index."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.stock_market
        self.rng = random.Random(f"stocks-{seed}")
        self.sentiment: dict[str, float] = {}
        self.value: dict[str, float] = {}
        self.target: dict[str, float] = {}
        self.prices: dict[str, float] = {}
        self._last_price: dict[str, float] = {}
        self._first_active: dict[str, int] = {}
        self._opened = False
        self._exempt: set[str] = set()
        self.listed: set[str] = set()
        self._ever: set[str] = set()
        self.daily_rows: list[dict[str, float]] = []
        self.index = self.cfg.index_base
        self._divisor: float | None = None
        self._event_pos = 0
        self.stats = {"listings": 0, "delistings": 0}
        self.etfs = EtfBook(self.cfg) if self.cfg.etfs_enabled else None

    def fundamental(self, runner: SimulationRunner, state: RunState, firm_id: str) -> float:
        groups = getattr(runner, "holding_groups", None)
        group_inputs = groups.fundamental_inputs(runner, state, firm_id) if groups is not None else None
        if groups is not None:
            # After a dissolution the series continues under the remaining firm.
            owner = groups.owner_of_listing(firm_id)
            rt = runner.env.runtimes[owner]
        else:
            owner, rt = firm_id, runner.env.runtimes[firm_id]
        if group_inputs is not None:
            # A holding is valued on its consolidated profit and cash.
            mean_profit, group_cash = group_inputs
        else:
            profits = [s[owner].profit for s in state.summaries[-2:] if owner in s]
            mean_profit = sum(profits) / len(profits) if profits else 0.0
            group_cash = max(0.0, rt.cash)
        rate = runner.env.central_bank.policy_rate if runner.config.central_bank.enabled else 0.01
        multiple = max(self.cfg.min_multiple,
                       min(self.cfg.max_multiple,
                           self.cfg.base_multiple * (1 - self.cfg.rate_sensitivity * (rate - 0.01))))
        return max(0.01 * max(1.0, rt.initial_cash),
                   multiple * mean_profit + group_cash)

    @staticmethod
    def _name(runner: SimulationRunner, firm_id: str | None) -> str:
        if not firm_id:
            return ""
        try:
            return runner.network.firm(firm_id).name
        except Exception:
            return firm_id

    def delisting_reason(self, runner: SimulationRunner, state: RunState,
                         fid: str) -> tuple[str, str | None]:
        """Return (reason, successor id) for a delisted firm."""
        groups = getattr(runner, "holding_groups", None)
        if groups is not None:
            group = groups.group_of(fid)
            if group is None:
                group = groups.groups.get(groups.sub_of.get(fid, ""))
            if group is not None and fid != group.listing_id and group.dissolved_year is None:
                return "holding", group.id
        mergers = getattr(runner, "mergers", None)
        for row in getattr(mergers, "log", []) or []:
            if fid in row.get("parents", []):
                return "merger", row.get("new")
        for event in reversed(state.events):
            if event.get("firm") != fid:
                continue
            kind = event.get("event")
            if kind == "takeover":
                match = re.search(r"von (\S+)", str(event.get("details", "")))
                return "takeover", match.group(1) if match else None
            if kind == "bankruptcy":
                return "bankruptcy", None
        return "exit", None

    def market_cap(self) -> float:
        return sum(self.prices[fid] * self.cfg.shares_per_firm for fid in sorted(self.listed))

    def price(self, firm_id: str) -> float | None:
        return self.prices.get(firm_id) if firm_id in self.listed else None

    def daily(self, runner: SimulationRunner, state: RunState, year: int, day: int,
              global_day: int) -> None:
        cfg = self.cfg
        if not cfg.enabled:
            return

        # Apply shocks before this day's listings and delistings.
        for event in state.events[self._event_pos:]:
            firm_id = event.get("firm")
            if event.get("event") in cfg.event_shocks and firm_id in self.listed:
                self.sentiment[firm_id] = self.sentiment.get(firm_id, 0.0) + cfg.event_shocks[event["event"]]

        groups = getattr(runner, "holding_groups", None)
        # A holding keeps the series of its root firm alive; plain subsidiaries are not traded separately.
        active = sorted(fid for fid, rt in runner.env.runtimes.items()
                        if (rt.active and (groups is None or not groups.is_sub_only(fid)))
                        or (groups is not None and (groups.listing_alive(fid)
                            or (fid in groups.listing_owner and runner.env.runtimes[groups.listing_owner[fid]].active))))
        for fid in active:
            if fid not in self._first_active:
                self._first_active[fid] = year

        if year >= cfg.tradable_from_year and not self._opened:
            self._opened = True
            self._exempt = set(active)

        old_listed = set(self.listed)
        for fid in sorted(self.listed - set(active)):
            self.listed.remove(fid)
            self.stats["delistings"] += 1
            reason, successor = self.delisting_reason(runner, state, fid)
            name = self._name(runner, fid)
            if reason == "holding":
                group = groups.group_of(fid) if groups is not None else None
                holding = group.name if group is not None else (successor or "")
                text = f"von {holding} übernommen, gehandelt wird nur noch die Holding"
            elif reason == "merger":
                text = f"Fusion zu {self._name(runner, successor)}"
            elif reason == "takeover":
                text = f"übernommen von {self._name(runner, successor)}"
            elif reason == "bankruptcy":
                text = "Konkurs"
            else:
                text = "Marktaustritt"
            state.events.append({"year": year, "day": day, "firm": fid, "event": "delisted",
                                 "details": f"Aktie von {name} dekotiert: {text}",
                                 "reason": reason, "successor": successor})

        new_listings = []
        if year >= cfg.tradable_from_year:
            for fid in active:
                if (fid not in self.listed and fid not in self._ever
                        and (fid in self._exempt
                             or year - self._first_active[fid] >= cfg.listing_min_years)):
                    runtime = runner.env.runtimes[fid]
                    firm = runner.network.firm(fid)
                    capacity = firm.capacity
                    cost = (
                        runner.config.geography.build_cost_per_capacity_unit.get(firm.stage, 0.0)
                        * runner.long_run.price_index
                    )
                    book = max(0.0, runtime.cash) + capacity * cost
                    fundamental = self.fundamental(runner, state, fid)
                    value0 = max(fundamental, book)

                    self.listed.add(fid)
                    self._ever.add(fid)
                    self.value[fid] = value0
                    self.target[fid] = self.fundamental(runner, state, fid)
                    self.sentiment[fid] = 0.0
                    self.prices[fid] = value0 / cfg.shares_per_firm
                    self._last_price[fid] = self.prices[fid]
                    self.stats["listings"] += 1
                    new_listings.append(fid)

        if new_listings:
            if not old_listed and not self.daily_rows and self.stats["listings"] == len(new_listings):
                state.events.append({"year": year, "day": day, "firm": "", "event": "exchange_opened",
                                     "details": f"Börse eröffnet: {len(new_listings)} Firmen handelbar"})
            else:
                for fid in new_listings:
                    state.events.append({"year": year, "day": day, "firm": fid, "event": "listed",
                                         "details": f"{fid} neu an der Börse"})

        refresh = global_day % cfg.revalue_days == 0
        for fid in sorted(self.listed):
            if refresh or fid not in self.target:
                self.target[fid] = self.fundamental(runner, state, fid)
            target = self.target[fid]
            current_value = self.value.get(fid, target)
            self.value[fid] = current_value + cfg.value_adjust_rate * (target - current_value)

            draw = self.rng.gauss(0.0, 1.0)
            sentiment = (1 - cfg.reversion) * self.sentiment.get(fid, 0.0) + cfg.volatility * draw
            self.sentiment[fid] = max(-3.0, min(3.0, sentiment))
            raw = self.value[fid] * math.exp(self.sentiment[fid]) / cfg.shares_per_firm
            if fid in self._last_price:
                last = self._last_price[fid]
                price = min(max(raw, last * (1 - cfg.max_daily_move)),
                            last * (1 + cfg.max_daily_move))
            else:
                price = raw
            self.prices[fid] = price
            self._last_price[fid] = price

        cap = self.market_cap()
        if self.listed and cap > 0:
            if self._divisor is None:
                self._divisor = cap / cfg.index_base
            elif self.listed != old_listed:
                self._divisor = cap / self.index if self.index > 0 else cap / cfg.index_base
            elif self._divisor > 0:
                self.index = cap / self._divisor

        if self.listed:
            self.daily_rows.append({"global_day": global_day, "year": year, "day": day,
                                    "index": round(self.index, 4),
                                    **{fid: round(self.prices[fid], 4) for fid in sorted(self.listed)}})
            if self.etfs is not None:
                self.etfs.update({fid: runner.network.firm(fid) for fid in sorted(self.listed)},
                                 {fid: self.prices[fid] for fid in sorted(self.listed)}, global_day, year, day)

        # Events emitted above are already handled for this day.
        self._event_pos = len(state.events)

    def year_end_stats(self) -> dict[str, float | int]:
        return {"stock_index": self.index, "market_cap": self.market_cap(),
                "listed_firms": len(self.listed)}


class EtfBook:
    """Phase 23: chain-linked ETF levels per region, product category and stage (display only)."""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.definitions: dict[str, dict] = {}
        self.levels: dict[str, float] = {}
        self.rows: list[dict] = []
        self._last: dict[str, dict[str, float]] = {}
        self._last_weights: dict[str, dict[str, float]] = {}
        self._holdings: dict[str, dict[str, float]] = {}

    @staticmethod
    def groups_for(firm: object) -> list[tuple[str, str]]:
        groups = []
        region = getattr(firm, "region")
        stage = getattr(firm, "stage")
        channel = getattr(firm, "channel")
        category = getattr(firm, "category")

        if region:
            groups.append(("region", region))
        if stage == "factory":
            groups.append(("category", category))
        groups.append(("stage", "restaurant" if stage == "retailer" and channel == "restaurant" else stage))
        return groups

    def _capped_weights(self, ids: list[str], prices: dict[str, float]) -> dict[str, float]:
        """Basket weights: by market value (price, equal share counts) or equal.

        A weight cap is deliberately not applied: forcing penny stocks up to the cap
        and rebalancing harvests their swings and blew the ETF levels up to the millions.
        """
        if not ids:
            return {}

        bases = {
            fid: prices[fid] if self.cfg.etf_weighting == "market_cap" else 1.0
            for fid in ids
        }
        total = sum(bases.values())
        weights: dict[str, float] = {}
        assigned = 0.0
        for fid in ids[:-1]:
            weights[fid] = bases[fid] / total
            assigned += weights[fid]
        weights[ids[-1]] = 1.0 - assigned
        return weights

    def update(self, members: dict[str, object], prices: dict[str, float],
               global_day: int, year: int, day: int) -> None:
        current: dict[str, set[str]] = {}
        for firm_id in sorted(members):
            for kind, key in self.groups_for(members[firm_id]):
                # "branche" switches on the industry indices; they are the stage ETFs
                # (factory, distributor, wholesaler, retailer, restaurant), so not duplicated.
                # Banks and couriers are not listed and therefore have no index.
                if kind not in self.cfg.etf_groups and not (kind == "stage" and "branche" in self.cfg.etf_groups):
                    continue
                etf_id = f"{kind}:{key}"
                if etf_id not in self.definitions:
                    self.definitions[etf_id] = {
                        "id": etf_id,
                        "kind": kind,
                        "key": key,
                        "members": [],
                    }
                current.setdefault(etf_id, set()).add(firm_id)
                definition_members = self.definitions[etf_id]["members"]
                if firm_id not in definition_members:
                    definition_members.append(firm_id)
                    definition_members.sort()

        row = {"global_day": global_day, "year": year, "day": day}
        for etf_id in sorted(self.definitions):
            member_ids = current.get(etf_id, set())
            # Hysteresis: entry at the minimum price, exit only below half of it, so a
            # share hovering around the limit does not jump in and out ("buy high, sell low").
            held = self._holdings.get(etf_id, {})
            eligible = sorted(
                fid for fid in member_ids
                if prices.get(fid, 0.0) > 0 and (
                    prices.get(fid, 0.0) >= self.cfg.etf_min_price
                    or (fid in held and prices.get(fid, 0.0) >= 0.5 * self.cfg.etf_min_price))
            )
            if len(eligible) < self.cfg.etf_min_members:
                self._last[etf_id] = {}
                self._last_weights.pop(etf_id, None)
                self._holdings.pop(etf_id, None)
                continue

            # Buy-and-hold between rebalances: fixed share quantities, so the level follows
            # the basket value instead of a daily rebalanced mean of returns (which drifts
            # upwards with volatile prices and let the ETFs explode).
            holdings = self._holdings.get(etf_id, {})
            if etf_id not in self.levels:
                self.levels[etf_id] = self.cfg.etf_base
            else:
                # Members that just fell below the minimum price still count on their last move
                # (otherwise only the gains of penny stocks around the limit would be kept).
                common = sorted(fid for fid in holdings
                                if fid in member_ids and prices.get(fid, 0.0) > 0
                                and fid in self._last.get(etf_id, {}))
                if common:
                    before = sum(holdings[fid] * self._last[etf_id][fid] for fid in common)
                    after = sum(holdings[fid] * prices[fid] for fid in common)
                    if before > 0:
                        self.levels[etf_id] *= after / before

            # No periodic rebalancing (it harvests volatility and inflates the level). Only on
            # member changes: leavers are dropped, continuing members keep their quantities
            # (scaled pro rata) and newcomers enter with their target weight.
            if not holdings or set(holdings) != set(eligible):
                target = self._capped_weights(eligible, prices)
                keep = [fid for fid in eligible if fid in holdings]
                new = [fid for fid in eligible if fid not in holdings]
                kept_value = {fid: holdings[fid] * prices[fid] for fid in keep}
                total = sum(kept_value.values())
                if not keep or total <= 0:
                    self._holdings[etf_id] = {fid: target[fid] / prices[fid] for fid in eligible}
                else:
                    share = 1.0 - sum(target[fid] for fid in new)
                    new_holdings = {fid: share * kept_value[fid] / total / prices[fid] for fid in keep}
                    new_holdings.update({fid: target[fid] / prices[fid] for fid in new})
                    self._holdings[etf_id] = new_holdings
            self._last[etf_id] = {fid: prices[fid] for fid in eligible}
            self._last_weights[etf_id] = self._capped_weights(eligible, prices)
            row[etf_id] = round(self.levels[etf_id], 4)

        self.rows.append(row)

    def eligible_members(self, etf_id: str, prices: dict[str, float]) -> list[str]:
        definition = self.definitions.get(etf_id)
        if definition is None:
            return []

        return sorted(
            fid for fid in definition["members"]
            if prices.get(fid, 0.0) > 0 and prices.get(fid, 0.0) >= self.cfg.etf_min_price
        )

    def weights(self, etf_id: str, prices: dict[str, float]) -> dict[str, float]:
        eligible = self.eligible_members(etf_id, prices)
        if len(eligible) < self.cfg.etf_min_members:
            return {}

        return self._capped_weights(eligible, prices)
