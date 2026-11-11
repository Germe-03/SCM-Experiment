from __future__ import annotations

from dataclasses import dataclass
import random

from market_sim.kpi import chf


@dataclass
class LeasingConfig:
    enabled: bool = True
    down_payment: float = 0.10
    min_years: int = 4
    max_years: int = 6
    bank_margin: float = 0.015
    dealer_self_lease_cash: float = 5_000_000.0
    residual_share: float = 0.30
    dealer_risk_factor: float = 4.0
    default_sale_factor: float = 0.7
    buy_min_life_left: float = 0.30
    buy_cash_factor: float = 1.5


@dataclass
class LeaseOffer:
    lessor_id: str
    kind: str
    down_payment: float
    annual_rate: float
    years: int
    residual: float
    monthly_payment: float


def monthly_payment(financed: float, residual: float, rate: float, years: int) -> float:
    """Monatliche Abschreibung und Zins auf den durchschnittlichen Saldo."""
    months = years * 12
    return (financed - residual) / months + (financed + residual) / 2 * rate / 12


class LeasingBook:
    def __init__(self, cfg: LeasingConfig | None, banking, trucks,
                 days_per_year: int, seed: int) -> None:
        self.cfg = cfg or LeasingConfig()
        self.banking = banking
        self.trucks = trucks
        self.days_per_year = days_per_year
        self.days = days_per_year
        self.rng = random.Random(f"leasing-{seed}")
        self.contracts: list[dict] = []
        self.history: list[dict] = []
        self._contract_counter = 0
        self._day = 0
        self._year_stats = {
            "new": 0,
            "income": 0.0,
            "defaults": 0,
            "losses": 0.0,
            "by_kind": {"bank": 0.0, "dealer": 0.0},
        }

    def offer(self, env, firm_id: str, price: float, life_years: float,
              policy_rate: float, risk: float) -> LeaseOffer | None:
        draw = self.rng.random()
        if not self.cfg.enabled or price <= 0:
            return None

        runtime = env.runtimes[firm_id]
        years = max(self.cfg.min_years, min(self.cfg.max_years, round(life_years * 0.5)))
        down = price * self.cfg.down_payment
        financed = price - down
        residual = min(price * self.cfg.residual_share, financed * 0.9)

        dealers = self.trucks._active_dealers()
        candidates = [
            dealer for dealer in dealers
            if dealer.cash >= max(self.cfg.dealer_self_lease_cash, financed)
        ]
        richest = max(candidates, key=lambda dealer: dealer.cash) if candidates else None
        dealer_chosen = (
            richest is not None
            and draw < min(0.9, max(0.0, richest.margin) * self.cfg.dealer_risk_factor)
        )

        bank_offer = None
        terms, _reason = self.banking.loan_offer(
            firm_id, runtime, financed, "truck", policy_rate
        )
        if terms is not None:
            bank, rate, _years = terms
            annual_rate = rate + self.cfg.bank_margin
            bank_offer = LeaseOffer(
                bank.id,
                "bank",
                down,
                annual_rate,
                years,
                residual,
                monthly_payment(financed, residual, annual_rate, years),
            )

        # Phase 57b: a dealer leases only to creditworthy firms: the bank would lend,
        # or the firm earns money and could pay a third of the amount from its cash.
        creditworthy = terms is not None or (
            getattr(runtime, "profit", 0.0) > 0 and runtime.cash >= financed / 3
        )
        dealer_offer = None
        if richest is not None and creditworthy:
            annual_rate = (
                max(0.0, policy_rate)
                + self.cfg.bank_margin
                # risk = the firm's risk tolerance (0..1): a bolder lessee pays up to 3 % more.
                + 0.03 * min(1.0, max(0.0, risk))
            )
            dealer_offer = LeaseOffer(
                richest.id,
                "dealer",
                down,
                annual_rate,
                years,
                residual,
                monthly_payment(financed, residual, annual_rate, years),
            )

        if dealer_chosen and dealer_offer is not None:
            return dealer_offer
        if bank_offer is not None:
            return bank_offer
        return dealer_offer

    def _event(self, state, firm: str, event: str, details: str) -> None:
        state.events.append({
            "year": state.year,
            "day": self.days,
            "firm": firm,
            "event": event,
            "details": details,
        })

    @staticmethod
    def _dealer_cash(dealer, amount: float, reason: str) -> None:
        dealer.cash += amount
        runtime = getattr(dealer, "rt", None)
        if runtime is not None and runtime.active:
            runtime.adjust_cash(amount, reason)

    def start(self, env, state, firm_id: str, truck, dealer, offer: LeaseOffer) -> dict:
        self._contract_counter += 1
        price = (
            offer.down_payment / self.cfg.down_payment
            if self.cfg.down_payment
            else offer.down_payment + offer.residual
        )
        financed = price - offer.down_payment
        contract = {
            "id": f"L{self._contract_counter:04d}",
            "firm": firm_id,
            "lessor": offer.lessor_id,
            "kind": offer.kind,
            "truck": truck,
            "truck_id": truck.id,
            "type": truck.type,
            "price": price,
            "start_year": state.year,
            "years": offer.years,
            "rate": offer.annual_rate,
            "monthly": offer.monthly_payment,
            "residual": offer.residual,
            "outstanding": financed,
            "dep_per_month": (financed - offer.residual) / (offer.years * 12),
            "payments_left": offer.years * 12,
            "dealer_id": dealer.id if dealer is not None else None,
            "status": "active",
        }
        self.contracts.append(contract)
        truck.leased = True

        env.runtimes[firm_id].adjust_cash(
            -offer.down_payment, "leasing_anzahlung"
        )
        if offer.kind == "bank":
            self.banking.fund_lease(offer.lessor_id, financed)
        elif offer.kind == "dealer":
            lessor = self.trucks.dealers[offer.lessor_id]
            self._dealer_cash(lessor, -financed, "leasing_forderung")

        self._year_stats["new"] += 1
        self._event(
            state,
            firm_id,
            "lease_started",
            f"Leasing Lastwagen ({truck.type}) bei {offer.lessor_id}: "
            f"Anzahlung {chf(offer.down_payment)}, "
            f"Rate {chf(offer.monthly_payment)}/Monat, "
            f"{offer.years} Jahre, Zins {offer.annual_rate:.2%}",
        )
        return contract

    def daily(self, env) -> None:
        self._day += 1
        interval = max(1, round(self.days_per_year / 12))
        if not self.cfg.enabled or self._day % interval != 0:
            return

        for contract in self.contracts:
            if contract["status"] != "active" or contract["payments_left"] <= 0:
                continue
            runtime = env.runtimes.get(contract["firm"])
            if runtime is None or not runtime.active:
                continue

            pay = contract["monthly"]
            runtime.adjust_cash(-pay, "leasing_rate")
            if hasattr(runtime, "fixed_cost"):
                setattr(runtime, "fixed_cost", getattr(runtime, "fixed_cost") + pay)

            depreciation = contract["dep_per_month"]
            interest = pay - depreciation
            contract["outstanding"] = max(
                contract["residual"],
                contract["outstanding"] - depreciation,
            )
            contract["payments_left"] -= 1

            if contract["kind"] == "bank":
                self.banking.fund_lease(contract["lessor"], -depreciation)
                self.banking.book_lease_income(contract["lessor"], interest)
            elif contract["kind"] == "dealer":
                lessor = self.trucks.dealers.get(contract["lessor"])
                if lessor is not None:
                    self._dealer_cash(lessor, pay, "leasing_rate_eingang")

            self._year_stats["income"] += interest
            self._year_stats["by_kind"][contract["kind"]] += interest

    def _settle(self, contract: dict, proceeds: float,
                dealer_took_back: bool = False) -> None:
        remaining = contract["outstanding"]
        difference = proceeds - remaining

        if contract["kind"] == "bank":
            self.banking.fund_lease(contract["lessor"], -remaining)
            if difference > 0:
                self.banking.book_lease_income(contract["lessor"], difference)
            elif difference < 0:
                loss = -difference
                self.banking.book_lease_loss(contract["lessor"], loss)
                self._year_stats["losses"] += loss
        elif contract["kind"] == "dealer":
            lessor = self.trucks.dealers.get(contract["lessor"])
            if lessor is not None:
                if dealer_took_back:
                    amount = remaining
                    reason = "leasing_forderung"
                else:
                    amount = proceeds
                    reason = "leasing_verwertung"
                self._dealer_cash(lessor, amount, reason)

    def _successor(self, runner, state, firm_id: str) -> str | None:
        """Active successor of a firm that left by merger, takeover or holding (else None)."""
        market = getattr(runner, "stock_market", None)
        if market is None or not hasattr(market, "delisting_reason"):
            return None
        try:
            reason, successor = market.delisting_reason(runner, state, firm_id)
        except Exception:
            return None
        if reason not in ("merger", "takeover", "holding") or not successor:
            return None
        rt = runner.env.runtimes.get(successor)
        return successor if rt is not None and rt.active else None

    def year_end(self, runner, state) -> None:
        env = runner.env
        year = state.year

        for contract in sorted(
            (item for item in self.contracts if item["status"] == "active"),
            key=lambda item: item["id"],
        ):
            firm_id = contract["firm"]
            runtime = env.runtimes.get(firm_id)
            truck = contract["truck"]

            if runtime is None or not runtime.active:
                successor = self._successor(runner, state, firm_id)
                if successor is not None:
                    # Merger or takeover: the successor takes over contract and truck.
                    moved = self.trucks.remove_truck(firm_id, truck.id) if hasattr(self.trucks, "remove_truck") else None
                    self.trucks.fleets.setdefault(successor, []).append(moved or truck)
                    (moved or truck).owner = successor
                    contract["firm"] = successor
                    self._event(state, successor, "lease_transferred",
                                f"Leasingvertrag von {firm_id} übernommen")
                    continue
                remaining = contract["outstanding"]
                proceeds = self.trucks.value(env, truck) * self.cfg.default_sale_factor
                if hasattr(self.trucks, "remove_truck"):
                    self.trucks.remove_truck(firm_id, truck.id)
                loss = max(0.0, remaining - proceeds)

                if contract["kind"] == "bank":
                    self.banking.fund_lease(contract["lessor"], -remaining)
                    self.banking.book_lease_loss(contract["lessor"], loss)
                    if proceeds > remaining:
                        self.banking.book_lease_income(
                            contract["lessor"], proceeds - remaining
                        )
                elif contract["kind"] == "dealer":
                    lessor = self.trucks.dealers.get(contract["lessor"])
                    if lessor is not None:
                        self._dealer_cash(lessor, proceeds, "leasing_verwertung")

                contract["status"] = "default"
                self._year_stats["defaults"] += 1
                self._year_stats["losses"] += loss
                self._event(
                    state,
                    firm_id,
                    "lease_default",
                    f"Leasing ausgefallen: Lastwagen zurückgenommen und als Occasion "
                    f"verkauft für {chf(proceeds)}, Verlust {chf(loss)}",
                )
                continue

            if year < contract["start_year"] + contract["years"]:
                continue

            life = self.trucks.types[truck.type].life_years
            life_left = 1 - truck.age / life if life > 0 else 0.0
            if (
                runtime.cash >= contract["residual"] * self.cfg.buy_cash_factor
                and life_left > self.cfg.buy_min_life_left
            ):
                runtime.adjust_cash(
                    -contract["residual"], "leasing_kauf_restwert"
                )
                truck.leased = False
                self._settle(contract, contract["residual"])
                contract["status"] = "bought"
                self._event(
                    state,
                    firm_id,
                    "lease_ended",
                    f"Leasing beendet: Lastwagen zum Restwert gekauft "
                    f"({chf(contract['residual'])})",
                )
                continue

            active_dealers = self.trucks._active_dealers()
            ordered_dealers = sorted(
                active_dealers, key=lambda item: (-item.cash, item.id)
            )
            dealer_id = (
                contract["dealer_id"]
                if contract["kind"] == "dealer"
                else None
            )
            dealer_order = []
            if dealer_id is not None:
                preferred = next(
                    (item for item in active_dealers if item.id == dealer_id),
                    None,
                )
                if preferred is not None:
                    dealer_order.append(preferred)
            dealer_order.extend(
                item for item in ordered_dealers
                if all(item.id != existing.id for existing in dealer_order)
            )

            selected_dealer_id = None
            for candidate in dealer_order:
                ok = self.trucks.take_back_leased(
                    env, state, truck, candidate.id
                )
                if ok is not False:
                    selected_dealer_id = candidate.id
                    break

            if selected_dealer_id is None:
                if hasattr(self.trucks, "remove_truck"):
                    self.trucks.remove_truck(firm_id, truck.id)
                proceeds = 0.0
            else:
                proceeds = getattr(self.trucks, "last_takeback_price", 0.0)

            if hasattr(truck, "leased"):
                truck.leased = False
            self._settle(
                contract,
                proceeds,
                dealer_took_back=(
                    selected_dealer_id == dealer_id and dealer_id is not None
                ),
            )
            contract["status"] = "returned"
            self._event(
                state,
                firm_id,
                "lease_ended",
                f"Leasing beendet: Lastwagen zurückgegeben "
                f"(Erlös {chf(proceeds)})",
            )

        active = sum(item["status"] == "active" for item in self.contracts)
        stats = self._year_stats
        self.history.append({
            "year": year,
            "active": active,
            "new": stats["new"],
            "income": round(stats["income"], 2),
            "defaults": stats["defaults"],
            "losses": round(stats["losses"], 2),
            "by_kind": {
                "bank": round(stats["by_kind"]["bank"], 2),
                "dealer": round(stats["by_kind"]["dealer"], 2),
            },
        })
        self._year_stats = {
            "new": 0,
            "income": 0.0,
            "defaults": 0,
            "losses": 0.0,
            "by_kind": {"bank": 0.0, "dealer": 0.0},
        }

    def export(self) -> dict:
        return {
            "contracts": [
                {
                    "id": contract["id"],
                    "firm": contract["firm"],
                    "lessor": contract["lessor"],
                    "kind": contract["kind"],
                    "type": contract["type"],
                    "price": round(contract["price"], 2),
                    "start_year": contract["start_year"],
                    "years": contract["years"],
                    "rate": round(contract["rate"], 6),
                    "status": contract["status"],
                }
                for contract in self.contracts
            ],
            "history": list(self.history),
        }
