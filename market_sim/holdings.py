"""Phase 10: minority stakes in other firms, dividends and sales of bad stakes."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from market_sim.kpi import chf

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class Holdings:
    """Stakes as (owner, target) -> share; bought, paid out and sold at year end."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.holdings
        self.rng = random.Random(f"holdings-{seed}")
        self.stakes: dict[tuple[str, str], float] = {}
        self.paid: dict[tuple[str, str], float] = {}
        self.history: list[dict[str, object]] = []
        self.stats = {"dividends": 0.0, "stakes_bought": 0, "stakes_sold": 0}

    def value(self, runner: SimulationRunner, state: RunState, firm_id: str) -> float:
        profits = [s[firm_id].profit for s in state.summaries[-2:] if firm_id in s]
        mean_profit = sum(profits) / len(profits) if profits else 0.0
        return max(0.0, self.cfg.profit_multiple * mean_profit + max(0.0, runner.env.runtimes[firm_id].cash))

    def held_share(self, owner: str, target: str) -> float:
        return self.stakes.get((owner, target), 0.0)

    def antitrust_partners(self, owner: str) -> list[str]:
        return [t for (o, t), s in self.stakes.items() if o == owner and s >= self.cfg.antitrust_stake]

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        cfg = self.cfg
        env = runner.env
        year = state.year
        day = runner.config.simulation.days_per_year
        summaries = state.summaries[-1]
        # Draws in a fixed order: one per firm, always.
        rolls = {f.id: (self.rng.random(), self.rng.random(), self.rng.random()) for f in runner._firms()}
        if not cfg.enabled:
            return
        # Dividends from profitable targets, sales of stakes in loss-making or closed targets.
        for (owner, target), share in sorted(self.stakes.items()):
            o_rt, t_rt = env.runtimes[owner], env.runtimes[target]
            if not o_rt.active:
                del self.stakes[(owner, target)]
                continue
            if not t_rt.active:
                del self.stakes[(owner, target)]
                self._log(year, owner, target, "stake_lost", share, 0.0)
                state.events.append({"year": year, "day": day, "firm": owner, "event": "stake_lost",
                                     "details": f"Beteiligung an {target} ({share:.0%}) wertlos"})
                continue
            profit = summaries[target].profit if target in summaries else 0.0
            if profit > 0:
                dividend = share * profit * cfg.payout_ratio
                t_rt.adjust_cash(-dividend)
                o_rt.adjust_cash(dividend)
                self.paid[(owner, target)] = self.paid.get((owner, target), 0.0) + dividend
                self.stats["dividends"] += dividend
            elif t_rt.consecutive_loss_years >= cfg.sell_after_loss_years:
                price = share * self.value(runner, state, target)
                o_rt.adjust_cash(price)
                del self.stakes[(owner, target)]
                self.stats["stakes_sold"] += 1
                self._log(year, owner, target, "stake_sold", share, price)
                state.events.append({"year": year, "day": day, "firm": owner, "event": "stake_sold",
                                     "details": f"verkauft {share:.0%} an {target} für {chf(price)}"})
        # New stakes: rich, profitable firms buy into profitable firms they do not own yet.
        candidates = [f for f in runner._firms() if env.runtimes[f.id].active and f.id in summaries
                      and summaries[f.id].profit > 0]
        for owner in sorted(candidates, key=lambda f: f.id):
            buy_roll, target_roll, size_roll = rolls[owner.id]
            o_rt = env.runtimes[owner.id]
            if buy_roll >= cfg.buy_probability or o_rt.cash <= 0:
                continue
            targets = [f for f in candidates if f.id != owner.id and (owner.id, f.id) not in self.stakes
                       and (f.id, owner.id) not in self.stakes]
            if not targets:
                continue
            target = targets[min(len(targets) - 1, int(target_roll * len(targets)))]
            share = round(cfg.min_stake + size_roll * (cfg.max_stake - cfg.min_stake), 2)
            owned = sum(s for (o, t), s in self.stakes.items() if t == target.id)
            share = min(share, 0.99 - owned)
            price = share * self.value(runner, state, target.id)
            if share < cfg.min_stake or price <= 0 or o_rt.cash < cfg.cash_cover * price:
                continue
            o_rt.adjust_cash(-price)
            env.runtimes[target.id].adjust_cash(price)  # fresh equity for the target
            self.stakes[(owner.id, target.id)] = share
            self.stats["stakes_bought"] += 1
            self._log(year, owner.id, target.id, "stake_bought", share, price)
            state.events.append({"year": year, "day": day, "firm": owner.id, "event": "stake_bought",
                                 "details": f"kauft {share:.0%} an {target.id} für {chf(price)}"})

    def _log(self, year, owner, target, action, share, price) -> None:
        self.history.append({"year": year, "owner": owner, "target": target, "action": action,
                             "share": share, "price": price, "dividends": self.paid.get((owner, target), 0.0)})

    def snapshot(self, year: int) -> list[dict[str, object]]:
        return [{"year": year, "owner": o, "target": t, "share": s, "dividends": self.paid.get((o, t), 0.0)}
                for (o, t), s in sorted(self.stakes.items())]
