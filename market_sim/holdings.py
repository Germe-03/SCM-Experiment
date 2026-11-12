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
        self.depot: dict[tuple[str, str], str] = {}
        self.history: list[dict[str, object]] = []
        self.stats = {"dividends": 0.0, "stakes_bought": 0, "stakes_sold": 0, "broker_fees": 0.0}

    def value(self, runner: SimulationRunner, state: RunState, firm_id: str) -> float:
        profits = [s[firm_id].profit for s in state.summaries[-2:] if firm_id in s]
        mean_profit = sum(profits) / len(profits) if profits else 0.0
        return max(0.0, self.cfg.profit_multiple * mean_profit + max(0.0, runner.env.runtimes[firm_id].cash))

    def market_value(self, runner: SimulationRunner, state: RunState, firm_id: str) -> float:
        market = runner.stock_market
        if self.cfg.via_bank and market is not None and market.price(firm_id) is not None:
            return market.price(firm_id) * market.cfg.shares_per_firm
        return self.value(runner, state, firm_id)

    def _broker(self, runner: SimulationRunner, owner_id: str, amount: float) -> tuple[float, str | None]:
        banking = runner.env.banking
        if self.cfg.via_bank and banking is not None and banking.accounts.get(owner_id):
            bank = banking.primary_bank(owner_id)
            fee = amount * self.cfg.broker_fee
            bank.fee_income += fee
            self.stats["broker_fees"] = self.stats.get("broker_fees", 0.0) + fee
            return fee, bank.id
        return 0.0, None

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
        # Dealers get their own draws after all firm draws, so runs without dealers stay unchanged.
        dealers = list(getattr(runner, "_dealers", lambda: [])())
        rolls.update({d.id: (self.rng.random(), self.rng.random(), self.rng.random()) for d in dealers})
        dealer_ids = {d.id for d in dealers}
        trucks = getattr(getattr(env, "geography", None), "trucks", None)
        fleets = getattr(trucks, "fleets", None) or {}
        if not cfg.enabled:
            return
        # Dividends from profitable targets, sales of stakes in loss-making or closed targets.
        for (owner, target), share in sorted(self.stakes.items()):
            o_rt, t_rt = env.runtimes[owner], env.runtimes[target]
            if not o_rt.active:
                del self.stakes[(owner, target)]
                self.depot.pop((owner, target), None)
                continue
            if not t_rt.active:
                del self.stakes[(owner, target)]
                self.depot.pop((owner, target), None)
                self._log(year, owner, target, "stake_lost", share, 0.0)
                state.events.append({"year": year, "day": day, "firm": owner, "event": "stake_lost",
                                     "details": f"Beteiligung an {target} ({share:.0%}) wertlos"})
                continue
            profit = summaries[target].profit if target in summaries else 0.0
            if profit > 0:
                dividend = share * profit * cfg.payout_ratio
                t_rt.adjust_cash(-dividend, f"dividende_an:{owner}")
                o_rt.adjust_cash(dividend, f"dividende_von:{target}")
                self.paid[(owner, target)] = self.paid.get((owner, target), 0.0) + dividend
                self.stats["dividends"] += dividend
            elif t_rt.consecutive_loss_years >= cfg.sell_after_loss_years:
                price = share * self.market_value(runner, state, target)
                market = runner.stock_market
                if (cfg.via_bank and market is not None and market.price(target) is not None
                        and share < cfg.small_stake_limit):
                    fee, bank_id = self._broker(runner, owner, price)
                    o_rt.adjust_cash(price - fee, f"beteiligung_verkauft:{target}")
                    bank_name = env.banking.banks[bank_id].name if bank_id is not None else None
                    details = (f"verkauft {share:.0%} an {target} über {bank_name} an der Börse "
                               f"für {chf(price)}" if bank_name is not None
                               else f"verkauft {share:.0%} an {target} für {chf(price)}")
                else:
                    o_rt.adjust_cash(price, f"beteiligung_verkauft:{target}")
                    details = f"verkauft {share:.0%} an {target} für {chf(price)}"
                del self.stakes[(owner, target)]
                self.depot.pop((owner, target), None)
                self.stats["stakes_sold"] += 1
                self._log(year, owner, target, "stake_sold", share, price)
                state.events.append({"year": year, "day": day, "firm": owner, "event": "stake_sold",
                                     "details": details})
        # New stakes: rich, profitable firms buy into profitable firms they do not own yet.
        players = set(getattr(runner, "player_choices", {}) or {})  # never automatic owners or targets
        candidates = [f for f in list(runner._firms()) + dealers if env.runtimes[f.id].active and f.id in summaries
                      and summaries[f.id].profit > 0 and f.id not in players]
        for owner in sorted(candidates, key=lambda f: f.id):
            buy_roll, target_roll, size_roll = rolls[owner.id]
            o_rt = env.runtimes[owner.id]
            if buy_roll >= cfg.buy_probability or o_rt.cash <= 0:
                continue
            targets = [f for f in candidates if f.id != owner.id and (owner.id, f.id) not in self.stakes
                       and (f.id, owner.id) not in self.stakes]
            if not targets:
                continue
            if owner.id in dealer_ids:
                # Dealers prefer the transport branch: other dealers and firms with their own fleet.
                transport = [f for f in targets if f.id in dealer_ids or fleets.get(f.id)]
                targets = transport or targets
            target = targets[min(len(targets) - 1, int(target_roll * len(targets)))]
            share = round(cfg.min_stake + size_roll * (cfg.max_stake - cfg.min_stake), 2)
            owned = sum(s for (o, t), s in self.stakes.items() if t == target.id)
            share = min(share, 0.99 - owned)
            market = runner.stock_market
            listed = market is not None and market.price(target.id) is not None
            small = cfg.via_bank and listed and share < cfg.small_stake_limit
            if cfg.via_bank and not listed and share < cfg.small_stake_limit:
                continue
            market_value = self.market_value(runner, state, target.id)
            if small:
                price = share * market_value
                banking = env.banking
                expected_fee = (price * cfg.broker_fee
                                if banking is not None and banking.accounts.get(owner.id) else 0.0)
                if (share < cfg.min_stake or price <= 0
                        or o_rt.cash < cfg.cash_cover * (price + expected_fee)
                        or not env.can_spend(owner.id, price + expected_fee)):
                    continue
                fee, bank_id = self._broker(runner, owner.id, price)
                o_rt.adjust_cash(-(price + fee), f"beteiligung:{target.id}")
                market.sentiment[target.id] += cfg.price_impact * share
                self.depot[(owner.id, target.id)] = bank_id or ""
                bank_name = env.banking.banks[bank_id].name if bank_id is not None else "die Bank"
                details = (f"kauft {share:.0%} an {target.id} über {bank_name} an der Börse "
                           f"für {chf(price)} (Gebühr {chf(fee)}, Aktien im Depot)")
            else:
                price = (share * market_value * (1 + cfg.control_premium)
                         if cfg.via_bank else share * self.value(runner, state, target.id))
                credit_financed = False
                if cfg.via_bank:
                    if o_rt.cash < cfg.cash_cover * price:
                        if not (o_rt.cash < price and env.can_spend(owner.id, price)):
                            continue
                        credit_financed = True
                    if not env.can_spend(owner.id, price):
                        continue
                else:
                    if share < cfg.min_stake or price <= 0 or o_rt.cash < cfg.cash_cover * price:
                        continue
                    if not env.can_spend(owner.id, price):
                        continue
                if share < cfg.min_stake or price <= 0:
                    continue
                o_rt.adjust_cash(-price, f"beteiligung:{target.id}")
                env.runtimes[target.id].adjust_cash(price, f"kapital_von:{owner.id}")  # fresh equity for the target
                details = f"kauft {share:.0%} an {target.id} für {chf(price)}"
                if credit_financed:
                    details += " (mit Kredit der Hausbank finanziert)"
            self.stakes[(owner.id, target.id)] = share
            self.stats["stakes_bought"] += 1
            self._log(year, owner.id, target.id, "stake_bought", share, price)
            state.events.append({"year": year, "day": day, "firm": owner.id, "event": "stake_bought",
                                 "details": details})

    def _log(self, year, owner, target, action, share, price) -> None:
        self.history.append({"year": year, "owner": owner, "target": target, "action": action,
                             "share": share, "price": price, "dividends": self.paid.get((owner, target), 0.0)})

    def snapshot(self, year: int) -> list[dict[str, object]]:
        return [{"year": year, "owner": o, "target": t, "share": s,
                 "dividends": self.paid.get((o, t), 0.0), "custodian": self.depot.get((o, t), "")}
                for (o, t), s in sorted(self.stakes.items())]
