"""Monetary policy and commercial bank accounts."""

from dataclasses import dataclass
import random

from market_sim.config import BankingConfig, CentralBankConfig
from market_sim.kpi import BankAnnualReport, chf


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
    credit_rejections: int = 0
    fee_income: float = 0.0
    active: bool = True
    founded_year: int = 0
    failed_year: int = 0
    # Phase 55: yearly figures of investment loans and deposit interest.
    new_loans: float = 0.0
    new_loan_count: int = 0
    loan_interest: float = 0.0
    loan_write_offs: float = 0.0
    deposit_interest_paid: float = 0.0
    negative_interest_income: float = 0.0
    # Leasing: receivables count like loans (added to `loans` by aggregate/spending_limit).
    lease_receivables: float = 0.0
    lease_income: float = 0.0
    lease_losses: float = 0.0

    @property
    def balance_total(self) -> float:
        """Bilanzsumme: assets are loans plus SNB reserves (deposits + equity - loans, if positive);
        liabilities are deposits, equity and SNB refinancing for any shortfall. Both sides equal
        max(loans, deposits + equity)."""
        return max(0.0, self.loans, self.deposits + self.equity)

    @property
    def capital_ratio(self) -> float:
        """Eigenkapitalquote = Eigenkapital / Bilanzsumme (reports and dashboard)."""
        total = self.balance_total
        return self.equity / total if total > 0 else 0.0

    @property
    def risk_weighted_ratio(self) -> float:
        """Equity / loans: SNB reserves carry no risk weight, so only loans count. Lending
        limit, payout and the firms' safety judgement keep using this ratio (as before Phase 33)."""
        # A debt-free bank has no capital requirement; keep CSV values finite.
        return self.equity / self.loans if self.loans > 0 else (1.0 if self.equity > 0 else 0.0)


@dataclass
class Loan:
    """Phase 55: investment loan with a fixed rate and equal yearly principal repayments."""

    id: str
    firm_id: str
    bank_id: str
    principal: float
    outstanding: float
    rate: float
    years: int
    installment: float
    year: int
    purpose: str


PURPOSE_DE = {
    "expand": "Ausbau", "site": "neuen Standort", "truck": "Lastwagen",
    "takeover": "Übernahme", "rnd": "F&E-Projekt", "stake": "Beteiligung",
}


def deposit_threshold(config, runtime, price_index: float) -> float:
    return max(config.deposit_threshold_min * price_index,
               config.deposit_threshold_revenue_fraction * runtime.last_year_revenue)


class BankingSystem:
    def __init__(self, config: BankingConfig, seed: int, runtimes: dict) -> None:
        self.cfg = config
        self._rng = random.Random(f"banking-{seed}")
        equity = sum(r.initial_cash for r in runtimes.values()) * config.start_equity_fraction / len(config.banks)
        self.start_equity = equity
        self.banks = {b.id: CommercialBank(b.id, b.name, b.margin, equity)
                      for b in sorted(config.banks, key=lambda b: b.id)}
        self.failures: list[dict] = []
        self.last_founding_year: int | None = None
        # Firms whose credit was called after a failure: their old debt stays with the failed bank.
        self.called: set[str] = set()
        # Insertion order preserves the primary (credit) bank, regardless of shares.
        self.accounts: dict[str, dict[str, float]] = {}
        self.credit_events: list[dict] = []
        self.rejected_year: dict[str, int] = {}
        # Phase 55: investment loans and their own random stream (preference for credit, rate damping).
        self.loans: dict[str, Loan] = {}
        self.by_firm: dict[str, list[Loan]] = {}
        self._term_cache: dict[str, float] | None = None
        self._loan_counter = 0
        self.loan_rng = random.Random(f"loans-{seed}")
        for firm_id in sorted(runtimes):
            if runtimes[firm_id].active:
                self.add_firm(firm_id)
        self.aggregate(runtimes)

    def term_debt(self, firm_id: str) -> float:
        return sum(loan.outstanding for loan in self.by_firm.get(firm_id, ()))

    def bank_term_loans(self, bank_id: str) -> float:
        if self._term_cache is None:
            cache: dict[str, float] = {}
            for loan in self.loans.values():
                cache[loan.bank_id] = cache.get(loan.bank_id, 0.0) + loan.outstanding
            self._term_cache = cache
        return self._term_cache.get(bank_id, 0.0)

    def _drop_loan(self, loan: Loan) -> None:
        self._term_cache = None
        self.loans.pop(loan.id, None)
        owned = self.by_firm.get(loan.firm_id)
        if owned is not None and loan in owned:
            owned.remove(loan)
            if not owned:
                del self.by_firm[loan.firm_id]

    def primary_bank(self, firm_id: str) -> CommercialBank:
        return self.banks[next(iter(self.accounts[firm_id]))]

    def room(self, bank) -> float:
        return max(0.0, bank.equity / self.cfg.min_capital_ratio - bank.loans) if bank.active else 0.0

    def choose_bank(self, firm_id: str, runtimes: dict, exclude: set[str],
                    noise: dict[str, float]) -> str | None:
        cfg = self.cfg
        debt = max(0.0, -runtimes[firm_id].cash)
        candidates = [bid for bid in sorted(self.banks)
                      if self.banks[bid].active and bid not in exclude
                      and (debt == 0 or debt <= self.room(self.banks[bid]))]
        if not candidates:
            return None

        def score(bid):
            bank = self.banks[bid]
            return (-cfg.interest_weight * bank.margin
                    + cfg.safety_weight * max(-1.0, min(1.0, bank.risk_weighted_ratio))
                    + cfg.random_weight * noise[bid])

        return max(candidates, key=score)

    def spending_limit(self, firm_id: str, runtimes: dict, balances: dict[str, float],
                       amount: float, year: int, day: int) -> float:
        """Use current booked balances, including purchases earlier in this tick."""
        if not self.accounts.get(firm_id):
            return max(0.0, balances[firm_id])
        for bank in self.banks.values():
            bank.loans = (self.bank_term_loans(bank.id) + bank.lease_receivables) if bank.active else 0.0
        for fid, cash in balances.items():
            if runtimes[fid].active and self.accounts.get(fid) and fid not in self.called:
                self.primary_bank(fid).loans += max(0.0, -cash)
        cash = balances[firm_id]
        debt = max(0.0, -cash)
        wanted = max(debt, runtimes[firm_id].credit_limit)
        bank = self.primary_bank(firm_id)

        def room(candidate):
            return max(0.0, candidate.equity / self.cfg.min_capital_ratio - candidate.loans) if candidate.active else 0.0

        line = min(wanted, debt + room(bank))
        if amount > cash + line and line < wanted:
            self.reject(firm_id, bank, line, year, day)
            shares = self.accounts[firm_id]
            candidates = [bid for bid in shares if bid != bank.id]
            if self.cfg.second_account_enabled and len(shares) < self.cfg.max_accounts:
                candidates += [bid for bid in sorted(self.banks) if bid not in shares]
            # The new lender must also have room for the transferred debt.
            for bid in candidates:
                other = self.banks[bid]
                new_line = min(wanted, room(other))
                if new_line <= line or new_line < debt:
                    continue
                if bid not in shares:
                    shares[bank.id] = 1 - self.cfg.second_account_share
                    shares[bid] = self.cfg.second_account_share
                    self.credit_events.append({"year": year, "day": day, "firm": firm_id,
                        "event": "account_opened", "details": f"Zweitkonto bei {other.name} wegen Kreditklemme eröffnet"})
                self.accounts[firm_id] = {bid: shares[bid], **{k: v for k, v in shares.items() if k != bid}}
                bank.loans -= debt
                other.loans += debt
                self.credit_events.append({"year": year, "day": day, "firm": firm_id,
                    "event": "bank_switched", "details": f"Kreditbank von {bank.name} zu {other.name} gewechselt"})
                bank, line = other, new_line
                break
        budget = max(0.0, cash + line)
        if amount > budget:
            self.reject(firm_id, bank, line, year, day)
        return budget

    # -- Phase 55: investment loans ------------------------------------------
    def lending_room(self, bank: CommercialBank) -> float:
        """How much more the bank may lend: capital ratio and share of its funding."""
        if not bank.active:
            return 0.0
        lc = self.cfg.loans
        by_capital = bank.equity / self.cfg.min_capital_ratio - bank.loans
        by_funding = lc.max_loans_to_funding * max(0.0, bank.deposits + bank.equity) - bank.loans
        return max(0.0, min(by_capital, by_funding))

    def loan_offer(self, firm_id: str, runtime, amount: float, purpose: str, policy_rate: float):
        """Return (loan terms or None, reason). Terms: (bank, rate, years)."""
        lc = self.cfg.loans
        if not self.accounts.get(firm_id) or firm_id in self.called:
            return None, "keine Bank"
        bank = self.primary_bank(firm_id)
        revenue = max(runtime.last_year_revenue, 1.0)
        overdraft = max(0.0, -runtime.cash)
        term = self.term_debt(firm_id)
        if runtime.consecutive_loss_years >= 2:
            return None, "Verluste"
        if (overdraft + term + amount) / revenue > lc.max_debt_to_revenue:
            return None, "Verschuldung"
        equity_part = max(0.0, runtime.cash)
        total = equity_part + overdraft + term
        equity_quota = equity_part / total if total > 0 else 1.0
        premium = (lc.risk_premium_base
                   + lc.risk_premium_equity * (1.0 - equity_quota)
                   + lc.risk_premium_loss * runtime.consecutive_loss_years
                   + lc.risk_premium_debt * min(1.0, (overdraft + term) / revenue))
        rate = min(lc.max_rate, max(0.0, policy_rate) + bank.margin + premium)
        if rate > lc.max_acceptable_rate:
            return None, "Zins"
        room = self.lending_room(bank)
        if room < amount:
            return (None, f"Bank:{room}")
        years = lc.years.get(purpose, lc.default_years)
        return (bank, rate, years), ""

    def grant_loan(self, firm_id: str, runtime, bank: CommercialBank, amount: float, rate: float,
                   years: int, purpose: str, year: int, day: int, events: list) -> Loan:
        self._loan_counter += 1
        loan = Loan(f"K{self._loan_counter:05d}", firm_id, bank.id, amount, amount, rate, years,
                    amount / years, year, purpose)
        self.loans[loan.id] = loan
        self._term_cache = None
        self.by_firm.setdefault(firm_id, []).append(loan)
        runtime.adjust_cash(amount, "bank:Investitionskredit")
        bank.loans += amount
        bank.new_loans += amount
        bank.new_loan_count += 1
        events.append({"year": year, "day": day, "firm": firm_id, "event": "loan_granted",
                       "details": f"{bank.name}: Investitionskredit {chf(amount)} für {PURPOSE_DE.get(purpose, purpose)}, "
                                  f"{years} Jahre, Zins {rate:.2%}"})
        return loan

    def accrue_loan_interest(self, firm_id: str) -> float:
        """One day of interest on the firm's investment loans (booked to the bank's income)."""
        total = 0.0
        for loan in self.by_firm.get(firm_id, ()):
            interest = loan.outstanding * loan.rate / 365
            total += interest
            bank = self.banks.get(loan.bank_id)
            if bank is not None:
                bank.interest_income += interest
                bank.loan_interest += interest
        return total

    def repay_loans(self, runtimes: dict, year: int) -> None:
        """Yearly instalment; the first one falls due a year after the loan was granted."""
        for loan_id in sorted(self.loans):
            loan = self.loans[loan_id]
            if loan.year >= year:
                continue
            runtime = runtimes.get(loan.firm_id)
            if runtime is None or not runtime.active:
                continue
            pay = min(loan.installment, loan.outstanding)
            runtime.adjust_cash(-pay, "bank:Kredit getilgt")
            loan.outstanding -= pay
            self._term_cache = None
            if loan.outstanding < 1.0:
                self._drop_loan(loan)

    # -- leasing ---------------------------------------------------------------
    def fund_lease(self, bank_id: str, amount: float) -> None:
        """Receivable from a lease: positive amount = bank pays a truck, negative = repayment."""
        bank = self.banks.get(bank_id)
        if bank is None:
            return
        bank.lease_receivables = max(0.0, bank.lease_receivables + amount)
        if bank.active:
            bank.loans = self.bank_term_loans(bank.id) + bank.lease_receivables

    def book_lease_income(self, bank_id: str, amount: float) -> None:
        bank = self.banks.get(bank_id)
        if bank is not None:
            bank.interest_income += amount
            bank.lease_income += amount

    def book_lease_loss(self, bank_id: str, amount: float) -> None:
        bank = self.banks.get(bank_id)
        if bank is not None and amount > 0:
            bank.write_offs += amount
            bank.lease_losses += amount

    def reject(self, firm_id: str, bank: CommercialBank, line: float, year: int, day: int) -> None:
        if self.rejected_year.get(firm_id) == year:
            return
        self.rejected_year[firm_id] = year
        bank.credit_rejections += 1
        self.credit_events.append({"year": year, "day": day, "firm": firm_id,
            "event": "credit_rejected", "details": f"{bank.name}: Kredit abgelehnt, Linie {chf(line)}"})

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
        if self.accounts.get(firm_id) and firm_id not in self.called:
            self.primary_bank(firm_id).write_offs += max(0.0, amount) * self.cfg.loss_given_default

    def write_off_loans(self, firm_id: str) -> float:
        """Phase 55: the bank writes off the remaining principal of a bankrupt firm's loans."""
        total = 0.0
        for loan in list(self.by_firm.get(firm_id, ())):
            self._drop_loan(loan)
            loss = loan.outstanding * self.cfg.loss_given_default
            bank = self.banks.get(loan.bank_id)
            if bank is not None:
                bank.write_offs += loss
                bank.loan_write_offs += loss
            total += loan.outstanding
        return total

    def transfer_loans(self, old_id: str, new_id: str) -> None:
        """Phase 55: a buyer takes over the loans of a firm it absorbs."""
        for loan in self.by_firm.pop(old_id, []):
            loan.firm_id = new_id
            self.by_firm.setdefault(new_id, []).append(loan)

    def remove_firm(self, firm_id: str, cash: float) -> None:
        # Removing the account makes repeated close calls harmless.
        self.write_off(firm_id, -cash)
        self.write_off_loans(firm_id)
        self.accounts.pop(firm_id, None)

    def book_interest(self, firm_id: str, debt: float, cost: float, negative: float) -> None:
        if not self.accounts.get(firm_id):
            return
        if debt:
            self.primary_bank(firm_id).interest_income += cost
        else:
            for bank_id, share in self.accounts[firm_id].items():
                self.banks[bank_id].interest_income += negative * share
                self.banks[bank_id].interest_expense += (negative - cost) * share
                self.banks[bank_id].negative_interest_income += negative * share
                self.banks[bank_id].deposit_interest_paid += (negative - cost) * share

    def aggregate(self, runtimes: dict) -> None:
        for bank in self.banks.values():
            if bank.active:
                bank.loans = self.bank_term_loans(bank.id) + bank.lease_receivables
            bank.deposits = 0.0
        for firm_id in sorted(self.accounts):
            if not self.accounts[firm_id]:
                continue
            runtime = runtimes[firm_id]
            if not runtime.active:
                continue
            if firm_id not in self.called:
                self.primary_bank(firm_id).loans += max(0.0, -runtime.cash)
            for bank_id, share in self.accounts[firm_id].items():
                self.banks[bank_id].deposits += max(0.0, runtime.cash) * share

    def daily(self, runtimes: dict, policy_rate: float) -> None:
        self.aggregate(runtimes)
        for bank in self.banks.values():
            if bank.active:
                gap = bank.loans - bank.deposits - bank.equity
                if gap < 0 and policy_rate < 0:
                    # SNB exemption (Freibetrag): most reserves are spared the negative rate.
                    gap *= 1 - self.cfg.reserve_exemption
                bank.refinancing_cost += gap * policy_rate / 365
                bank.operating_cost += (bank.loans + bank.deposits) * self.cfg.operating_cost_rate / 365

    def fail_bank(self, bank, runtimes: dict, year: int, day: int, events: list) -> None:
        bank.active = False
        bank.failed_year = year
        insured_share = self.cfg.insured_share
        customers = 0
        deposits = 0.0
        total_loss = 0.0
        for firm_id in sorted(self.accounts):
            if bank.id not in self.accounts[firm_id]:
                continue
            noise = {bid: self._rng.random() for bid in sorted(self.banks)}
            runtime = runtimes[firm_id]
            shares = self.accounts[firm_id]
            share = shares[bank.id]
            deposit = max(0.0, runtime.cash) * share
            loss = deposit * (1 - insured_share)
            if loss > 0:
                runtime.adjust_cash(-loss, f"bankpleite:{bank.id}")
            was_primary = self.primary_bank(firm_id) is bank
            del shares[bank.id]
            debt = max(0.0, -runtime.cash)
            customers += 1
            deposits += deposit
            total_loss += loss

            if shares:
                other = next(iter(shares))
                self.accounts[firm_id] = {other: 1.0}
                if was_primary and debt > 0 and self.room(self.banks[other]) < debt:
                    new = self.choose_bank(firm_id, runtimes, {bank.id, other}, noise)
                    if new is not None:
                        self.accounts[firm_id] = {new: 0.5, other: 0.5}
                    else:
                        runtime.credit_limit = min(runtime.credit_limit, max(0.0, -runtime.cash))
                new_bank = self.banks[next(iter(self.accounts[firm_id]))]
            else:
                new = self.choose_bank(firm_id, runtimes, {bank.id}, noise)
                if new is None:
                    candidates = [bid for bid in sorted(self.banks)
                                  if self.banks[bid].active]
                    if not candidates:
                        self.accounts[firm_id] = {}
                        continue

                    def score(bid):
                        candidate = self.banks[bid]
                        return (-self.cfg.interest_weight * candidate.margin
                                + self.cfg.safety_weight * max(-1.0, min(1.0, candidate.risk_weighted_ratio))
                                + self.cfg.random_weight * noise[bid])

                    new = max(candidates, key=score)
                    runtime.credit_limit = 0.0
                    self.called.add(firm_id)
                self.accounts[firm_id] = {new: 1.0}
                new_bank = self.banks[new]

            for loan in self.by_firm.get(firm_id, ()):
                if loan.bank_id == bank.id and self.accounts.get(firm_id):
                    loan.bank_id = new_bank.id
                    self._term_cache = None
            events.append({"year": year, "day": day, "firm": firm_id, "event": "bank_switched",
                           "details": f"{bank.name} ist pleite: {chf(loss)} Guthaben verloren "
                                      f"(nur {insured_share:.0%} gesichert), neue Bank {new_bank.name}"})

        events.append({"year": year, "day": day, "firm": bank.id, "event": "bank_failed",
                       "details": f"{bank.name} ist pleite: {customers} Kunden, Einlagen "
                                  f"{chf(deposits)}, davon {insured_share:.0%} gesichert, "
                                  f"Verlust der Firmen {chf(total_loss)}"})
        self.failures.append({"year": year, "bank_id": bank.id, "customers": customers,
                              "deposits": deposits, "firm_losses": total_loss})

    def resolve_failures(self, runtimes: dict, year: int, day: int, events: list) -> None:
        max_failure_rounds = self.cfg.max_failure_rounds
        for _ in range(max_failure_rounds):
            failing = [self.banks[bid] for bid in sorted(self.banks)
                       if self.banks[bid].active and self.banks[bid].equity < 0]
            if not failing:
                break
            for bank in failing:
                if bank.active:
                    self.fail_bank(bank, runtimes, year, day, events)

    def enter_bank(self, runtimes: dict, price_index: float, year: int, day: int, events: list) -> None:
        roll = self._rng.random()
        margin_roll = self._rng.random()
        entry_enabled = self.cfg.entry_enabled
        max_banks = self.cfg.max_banks
        entry_probability = self.cfg.entry_probability
        entry_min_roe = self.cfg.entry_min_roe
        entry_rejections = self.cfg.entry_rejections
        entry_names = self.cfg.entry_names
        entry_margin = self.cfg.entry_margin
        if not entry_enabled:
            return
        active = [bank for bank in self.banks.values() if bank.active]
        if len(active) >= max_banks:
            return
        # Phase 36: Wartezeit zwischen Gründungen, entfällt bei wenigen aktiven Banken.
        if (len(active) >= self.cfg.waiting_waived_below and self.last_founding_year is not None
                and year - self.last_founding_year < self.cfg.min_years_between_foundings):
            return
        rejections = sum(bank.credit_rejections for bank in active)
        profitable = [bank for bank in active if bank.equity > 0]
        roe = sum(bank.year_profit / max(1, bank.equity) for bank in profitable) / len(profitable) if profitable else 0
        if not ((len(active) < len(self.cfg.banks)) or roe >= entry_min_roe
                or rejections >= entry_rejections) or roll >= entry_probability:
            return
        bank_id = f"B{len(self.banks) + 1}"
        used_names = {bank.name for bank in self.banks.values()}
        name = next((candidate for candidate in entry_names if candidate not in used_names),
                    f"Bank {len(self.banks) + 1}")
        margin = round(entry_margin * (0.75 + 0.5 * margin_roll), 4)
        equity = self.start_equity * price_index
        self.banks[bank_id] = CommercialBank(bank_id, name, margin, equity, founded_year=year)
        self.last_founding_year = year
        events.append({"year": year, "day": day, "firm": bank_id, "event": "bank_entry",
                       "details": f"{name} gegründet, Eigenkapital {chf(equity)}, "
                                  f"Marge {margin:.2%}"})
        # Firms left without any bank (all failed) become customers of the newcomer; old debt stays behind.
        for firm_id in sorted(self.accounts):
            if not self.accounts[firm_id] and runtimes[firm_id].active:
                self.accounts[firm_id] = {bank_id: 1.0}
                if runtimes[firm_id].cash < 0:
                    self.called.add(firm_id)

    def year_end(self, runtimes: dict, bank_config, price_index: float,
                 year: int, day: int, events: list) -> list[BankAnnualReport]:
        events.extend(self.credit_events)
        self.credit_events.clear()
        self.repay_loans(runtimes, year)
        self.aggregate(runtimes)
        for bank in self.banks.values():
            bank.year_profit = (bank.interest_income + bank.fee_income - bank.interest_expense - bank.refinancing_cost
                                - bank.operating_cost - bank.write_offs)
            bank.equity += bank.year_profit
            surplus = max(0.0, bank.equity - self.cfg.target_capital_ratio * bank.loans)
            payout = min(max(0.0, bank.year_profit) * self.cfg.payout_ratio, surplus)
            if payout > 0:
                bank.equity -= payout
                events.append({"year": year, "day": day, "firm": bank.id, "event": "bank_payout",
                               "details": f"{bank.name}: Ausschüttung {chf(payout)} verlässt das System"})
        self.resolve_failures(runtimes, year, day, events)
        self.enter_bank(runtimes, price_index, year, day, events)
        self.open_second_accounts(runtimes, bank_config, price_index, year, day, events)
        self.aggregate(runtimes)
        total_deposits = sum(b.deposits for b in self.banks.values() if b.active)
        total_loans = sum(b.loans for b in self.banks.values() if b.active)
        reports = [BankAnnualReport(
            customer_ids=sorted(fid for fid, accounts in self.accounts.items() if b.id in accounts),
            house_customer_ids=sorted(fid for fid, accounts in self.accounts.items()
                                      if next(iter(accounts), None) == b.id),
            house_customers=sum(next(iter(a), None) == b.id for a in self.accounts.values()),
            deposit_share=b.deposits / total_deposits if b.active and total_deposits else 0.0,
            loan_share=b.loans / total_loans if b.active and total_loans else 0.0,
            revenue=b.interest_income + b.fee_income,
            founded_year=b.founded_year, margin=b.margin,
            year=year, bank_id=b.id, name=b.name, equity=b.equity, loans=b.loans,
            deposits=b.deposits, capital_ratio=b.capital_ratio, profit=b.year_profit,
            balance_total=b.balance_total, risk_weighted_ratio=b.risk_weighted_ratio,
            interest_income=b.interest_income, interest_expense=b.interest_expense,
            refinancing_cost=b.refinancing_cost, operating_cost=b.operating_cost,
            write_offs=b.write_offs, customers=sum(b.id in a for a in self.accounts.values()),
            active=b.active,
            credit_rejections=b.credit_rejections,
            fee_income=b.fee_income,
            term_loans=self.bank_term_loans(b.id),
            new_loans=b.new_loans, new_loan_count=b.new_loan_count,
            loan_interest=b.loan_interest, loan_write_offs=b.loan_write_offs,
            deposit_interest_paid=b.deposit_interest_paid,
            negative_interest_income=b.negative_interest_income,
        ) for b in self.banks.values() if b.active or b.failed_year == year]
        for bank in self.banks.values():
            bank.interest_income = bank.interest_expense = bank.refinancing_cost = 0.0
            bank.operating_cost = bank.write_offs = 0.0
            bank.credit_rejections = 0
            bank.fee_income = 0.0
            bank.new_loans = bank.loan_interest = bank.loan_write_offs = 0.0
            bank.new_loan_count = 0
            bank.deposit_interest_paid = bank.negative_interest_income = 0.0
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
                    and primary.risk_weighted_ratio >= cfg.target_capital_ratio):
                continue
            candidates = [bid for bid in bank_ids if bid not in shares and self.banks[bid].active]
            if not candidates:
                continue

            def score(bid):
                bank = self.banks[bid]
                return (-cfg.interest_weight * bank.margin
                        + cfg.safety_weight * max(-1.0, min(1.0, bank.risk_weighted_ratio))
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
        self.year_index = 0
        self.change_years: list[int] = []
        self.last_emergency = False

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
        self.year_index += 1
        self.last_emergency = False
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
        new_rate = max(cfg.min_rate, min(cfg.max_rate,
                       max(old_rate - cfg.max_step, min(old_rate + cfg.max_step, target))))
        new_rate = round(new_rate, 12)
        if new_rate == old_rate:
            return False
        emergency = inflation > cfg.emergency_inflation
        recent = [y for y in self.change_years if y > self.year_index - cfg.window_years]
        self.change_years = recent
        if emergency:
            self.last_emergency = True
        elif len(recent) >= cfg.max_changes_per_window:
            return False
        else:
            self.change_years.append(self.year_index)
        self.policy_rate = new_rate
        return True
