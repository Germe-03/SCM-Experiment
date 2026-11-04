"""Monetary policy and commercial bank accounts."""

from dataclasses import dataclass
import random

from market_sim.config import BankingConfig, CentralBankConfig
from market_sim.kpi import BankAnnualReport


@dataclass
class CommercialBank:
    id: str
    name: str
    margin: float
    equity: float = 0.0
    loans: float = 0.0
    deposits: float = 0.0
    year_profit: float = 0.0
    interest_income: float = 0.0
    interest_expense: float = 0.0
    refinancing_cost: float = 0.0
    operating_cost: float = 0.0
    write_offs: float = 0.0
    active: bool = True
    founded_year: int = 0

    @property
    def capital_ratio(self) -> float:
        # A debt-free bank has no capital requirement; keep CSV values finite.
        return self.equity / self.loans if self.loans > 0 else (1.0 if self.equity > 0 else 0.0)


def deposit_threshold(config, runtime, price_index: float) -> float:
    return max(config.deposit_threshold_min * price_index,
               config.deposit_threshold_revenue_fraction * runtime.last_year_revenue)


class BankingSystem:
    def __init__(self, config: BankingConfig, seed: int, runtimes: dict) -> None:
        self.cfg = config
        self._rng = random.Random(f"banking-{seed}")
        equity = sum(r.initial_cash for r in runtimes.values()) * config.start_equity_fraction / len(config.banks)
        self.banks = {b.id: CommercialBank(b.id, b.name, b.margin, equity)
                      for b in sorted(config.banks, key=lambda b: b.id)}
        # Insertion order preserves the primary (credit) bank, regardless of shares.
        self.accounts: dict[str, dict[str, float]] = {}
        for firm_id in sorted(runtimes):
            if runtimes[firm_id].active:
                self.add_firm(firm_id)
        self.aggregate(runtimes)

    def primary_bank(self, firm_id: str) -> CommercialBank:
        return self.banks[next(iter(self.accounts[firm_id]))]

    def add_firm(self, firm_id: str) -> None:
        if firm_id in self.accounts:
            return
        counts = {bid: sum(bid in shares for shares in self.accounts.values())
                  for bid, bank in self.banks.items() if bank.active}
        if not counts:
            return
        least = min(counts.values())
        bank_id = self._rng.choice(sorted(bid for bid, count in counts.items() if count == least))
        self.accounts[firm_id] = {bank_id: 1.0}

    def write_off(self, firm_id: str, amount: float) -> None:
        if firm_id in self.accounts:
            self.primary_bank(firm_id).write_offs += max(0.0, amount)

    def remove_firm(self, firm_id: str, cash: float) -> None:
        # Removing the account makes repeated close calls harmless.
        self.write_off(firm_id, -cash)
        self.accounts.pop(firm_id, None)

    def book_interest(self, firm_id: str, debt: float, cost: float, negative: float) -> None:
        if debt:
            self.primary_bank(firm_id).interest_income += cost
        else:
            for bank_id, share in self.accounts[firm_id].items():
                self.banks[bank_id].interest_income += negative * share
                self.banks[bank_id].interest_expense += (negative - cost) * share

    def aggregate(self, runtimes: dict) -> None:
        for bank in self.banks.values():
            bank.loans = bank.deposits = 0.0
        for firm_id in sorted(self.accounts):
            runtime = runtimes[firm_id]
            if not runtime.active:
                continue
            self.primary_bank(firm_id).loans += max(0.0, -runtime.cash)
            for bank_id, share in self.accounts[firm_id].items():
                self.banks[bank_id].deposits += max(0.0, runtime.cash) * share

    def daily(self, runtimes: dict, policy_rate: float) -> None:
        self.aggregate(runtimes)
        for bank in self.banks.values():
            if bank.active:
                bank.refinancing_cost += (bank.loans - bank.deposits - bank.equity) * policy_rate / 365
                bank.operating_cost += (bank.loans + bank.deposits) * self.cfg.operating_cost_rate / 365

    def year_end(self, runtimes: dict, bank_config, price_index: float,
                 year: int, day: int, events: list) -> list[BankAnnualReport]:
        self.aggregate(runtimes)
        for bank in self.banks.values():
            bank.year_profit = (bank.interest_income - bank.interest_expense - bank.refinancing_cost
                                - bank.operating_cost - bank.write_offs)
            bank.equity += bank.year_profit
            surplus = max(0.0, bank.equity - self.cfg.target_capital_ratio * bank.loans)
            payout = min(max(0.0, bank.year_profit) * self.cfg.payout_ratio, surplus)
            if payout > 0:
                bank.equity -= payout
                events.append({"year": year, "day": day, "firm": bank.id, "event": "bank_payout",
                               "details": f"{bank.name}: Ausschüttung {payout:,.2f} CHF verlässt das System"})
        self.open_second_accounts(runtimes, bank_config, price_index, year, day, events)
        self.aggregate(runtimes)
        reports = [BankAnnualReport(
            year=year, bank_id=b.id, name=b.name, equity=b.equity, loans=b.loans,
            deposits=b.deposits, capital_ratio=b.capital_ratio, profit=b.year_profit,
            interest_income=b.interest_income, interest_expense=b.interest_expense,
            refinancing_cost=b.refinancing_cost, operating_cost=b.operating_cost,
            write_offs=b.write_offs, customers=sum(b.id in a for a in self.accounts.values()),
            active=b.active,
        ) for b in self.banks.values()]
        for bank in self.banks.values():
            bank.interest_income = bank.interest_expense = bank.refinancing_cost = 0.0
            bank.operating_cost = bank.write_offs = 0.0
        return reports

    def open_second_accounts(self, runtimes: dict, bank_config, price_index: float,
                             year: int, day: int, events: list) -> None:
        cfg = self.cfg
        if not cfg.second_account_enabled or cfg.max_accounts < 2:
            return
        bank_ids = sorted(self.banks)
        for firm_id in sorted(self.accounts):
            runtime = runtimes[firm_id]
            shares = self.accounts[firm_id]
            if not runtime.active or len(shares) != 1:
                continue
            # Fixed draws per eligible firm, including banks excluded from selection.
            noise = {bid: self._rng.random() for bid in bank_ids}
            primary = self.primary_bank(firm_id)
            if (runtime.cash <= deposit_threshold(bank_config, runtime, price_index)
                    and primary.capital_ratio >= cfg.target_capital_ratio):
                continue
            candidates = [bid for bid in bank_ids if bid not in shares and self.banks[bid].active]
            if not candidates:
                continue
            def score(bid):
                bank = self.banks[bid]
                return (-cfg.interest_weight * bank.margin
                        + cfg.safety_weight * max(-1.0, min(1.0, bank.capital_ratio))
                        + cfg.random_weight * noise[bid])
            second = max(candidates, key=score)
            shares[primary.id] = 1 - cfg.second_account_share
            shares[second] = cfg.second_account_share
            events.append({"year": year, "day": day, "firm": firm_id, "event": "account_opened",
                           "details": f"Zweitkonto bei {self.banks[second].name} eröffnet, "
                                      f"Guthabenanteil {cfg.second_account_share:.0%}"})


class CentralBank:
    def __init__(self, config: CentralBankConfig) -> None:
        self.cfg = config
        self.policy_rate = config.start_rate
        self.inflation = 0.0
        self.output_gap = 0.0
        self.demand_multiplier = 1.0

    @property
    def inflation_adjustment(self) -> float:
        cfg = self.cfg
        return max(-cfg.inflation_effect_cap,
                   min(cfg.inflation_effect_cap, cfg.inflation_effect * self.output_gap))

    def year_end(self, inflation: float, demand: float, expected: float) -> bool:
        """Set next year's rate and lagged demand effect, without random draws."""
        cfg = self.cfg
        if not cfg.enabled:
            return False
        old_rate = self.policy_rate
        self.inflation = inflation
        gap = demand / expected - 1 if expected > 0 else 0.0
        gap = max(-cfg.gap_cap, min(cfg.gap_cap, gap))
        self.output_gap += cfg.gap_smoothing * (gap - self.output_gap)
        # Demand next year responds to the rate in force this year.
        effect = -cfg.demand_effect * (old_rate - inflation - cfg.neutral_real_rate)
        self.demand_multiplier = 1 + max(-cfg.demand_effect_cap, min(cfg.demand_effect_cap, effect))
        target = (cfg.neutral_real_rate + inflation
                  + cfg.inflation_weight * (inflation - cfg.target_inflation)
                  + cfg.gap_weight * self.output_gap)
        target = round(target / 0.0025) * 0.0025
        self.policy_rate = max(cfg.min_rate, min(cfg.max_rate,
                               max(old_rate - cfg.max_step, min(old_rate + cfg.max_step, target))))
        self.policy_rate = round(self.policy_rate, 12)
        return self.policy_rate != old_rate
