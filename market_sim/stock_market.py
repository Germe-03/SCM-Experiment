"""Phase 17: listed firms, share prices and a chain-linked stock index."""

from __future__ import annotations

import math
import random
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
        self.prices: dict[str, float] = {}
        self.listed: set[str] = set()
        self._ever: set[str] = set()
        self.daily_rows: list[dict[str, float]] = []
        self.index = self.cfg.index_base
        self._divisor: float | None = None
        self._event_pos = 0
        self.stats = {"listings": 0, "delistings": 0}

    def fundamental(self, runner: SimulationRunner, state: RunState, firm_id: str) -> float:
        rt = runner.env.runtimes[firm_id]
        profits = [s[firm_id].profit for s in state.summaries[-2:] if firm_id in s]
        mean_profit = sum(profits) / len(profits) if profits else 0.0
        rate = runner.env.central_bank.policy_rate if runner.config.central_bank.enabled else 0.01
        multiple = max(self.cfg.min_multiple,
                       min(self.cfg.max_multiple,
                           self.cfg.base_multiple * (1 - self.cfg.rate_sensitivity * (rate - 0.01))))
        return max(0.01 * max(1.0, rt.initial_cash),
                   multiple * mean_profit + max(0.0, rt.cash))

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

        active = sorted(fid for fid, rt in runner.env.runtimes.items() if rt.active)
        old_listed = set(self.listed)
        for fid in sorted(self.listed - set(active)):
            self.listed.remove(fid)
            self.stats["delistings"] += 1
            state.events.append({"year": year, "day": day, "firm": fid, "event": "delisted",
                                 "details": f"Aktie von {fid} dekotiert"})

        new_listings = []
        if year >= cfg.tradable_from_year:
            for fid in active:
                if fid not in self.listed and fid not in self._ever:
                    self.listed.add(fid)
                    self._ever.add(fid)
                    self.value[fid] = self.fundamental(runner, state, fid)
                    self.sentiment[fid] = 0.0
                    self.prices[fid] = self.value[fid] / cfg.shares_per_firm
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
            if refresh or fid not in self.value:
                self.value[fid] = self.fundamental(runner, state, fid)
            draw = self.rng.gauss(0.0, 1.0)
            sentiment = (1 - cfg.reversion) * self.sentiment.get(fid, 0.0) + cfg.volatility * draw
            self.sentiment[fid] = max(-3.0, min(3.0, sentiment))
            self.prices[fid] = self.value[fid] * math.exp(self.sentiment[fid]) / cfg.shares_per_firm

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

        # Events emitted above are already handled for this day.
        self._event_pos = len(state.events)

    def year_end_stats(self) -> dict[str, float | int]:
        return {"stock_index": self.index, "market_cap": self.market_cap(),
                "listed_firms": len(self.listed)}
