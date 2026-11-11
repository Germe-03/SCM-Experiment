from __future__ import annotations


def _chf(value: float) -> str:
    return f"CHF {value:,.0f}".replace(",", "'")


def _policy_rate(env) -> float:
    try:
        policy_rate = getattr(env, "policy_rate", None)
        if callable(policy_rate):
            return float(policy_rate())
        central_bank = getattr(env, "central_bank", None)
        return float(getattr(central_bank, "policy_rate", 0.0)) if central_bank is not None else 0.0
    except Exception:
        return 0.0


def _offer_for_bank(banking, bank, firm_id, runtime, amount, purpose, policy_rate):
    """Prüft Kreditbedingungen für eine bestimmte Bank."""
    try:
        if not getattr(bank, "active", False):
            return None, None, "Bank nicht aktiv"

        lc = banking.cfg.loans
        if not banking.accounts.get(firm_id) or firm_id in banking.called:
            return None, None, "keine Bank"

        revenue = max(runtime.last_year_revenue, 1.0)
        overdraft = max(0.0, -runtime.cash)
        term = banking.term_debt(firm_id)
        if runtime.consecutive_loss_years >= 2:
            return None, None, "Verluste"
        if (overdraft + term + amount) / revenue > lc.max_debt_to_revenue:
            return None, None, "Verschuldung"

        equity_part = max(0.0, runtime.cash)
        total = equity_part + overdraft + term
        equity_quota = equity_part / total if total > 0 else 1.0
        premium = (
            lc.risk_premium_base
            + lc.risk_premium_equity * (1.0 - equity_quota)
            + lc.risk_premium_loss * runtime.consecutive_loss_years
            + lc.risk_premium_debt * min(1.0, (overdraft + term) / revenue)
        )
        rate = min(lc.max_rate, max(0.0, policy_rate) + bank.margin + premium)
        years = lc.years.get(purpose, lc.default_years)
        if rate > lc.max_acceptable_rate:
            return rate, years, "Zins"

        room = banking.lending_room(bank)
        if room < amount:
            return rate, years, f"Bank:{room}"
        return rate, years, ""
    except Exception:
        return None, None, "Kreditbedingungen nicht verfügbar"


def _loan_reason(reason: str) -> str:
    if reason == "Verluste":
        return "Zwei Verlustjahre in Folge"
    if reason == "Verschuldung":
        return "Zu hohe Verschuldung im Verhältnis zum Umsatz"
    if reason == "Zins":
        return "Zins wäre zu hoch"
    if reason.startswith("Bank:"):
        return "Bank hat nicht genug Spielraum"
    if reason == "keine Bank":
        return "Kein Bankkonto"
    return reason


def loan_offers(runner, firm_id, amount) -> list[dict]:
    """Gibt die Kreditangebote aller aktiven Banken zurück."""
    try:
        env = runner.env
        banking = getattr(env, "banking", None)
        if banking is None:
            return []
        runtime = env.runtimes[firm_id]
        policy_rate = _policy_rate(env)
        offers = []
        for bank in sorted(banking.banks.values(), key=lambda item: item.id):
            if not getattr(bank, "active", False):
                continue
            rate, years, reason = _offer_for_bank(
                banking, bank, firm_id, runtime, float(amount), "truck", policy_rate
            )
            offers.append({
                "bank_id": bank.id,
                "bank": bank.name,
                "rate": round(float(rate), 4) if rate is not None else None,
                "years": int(years) if years is not None else None,
                "ok": not bool(reason),
                "reason": _loan_reason(reason) if reason else "",
            })
        return offers
    except Exception:
        return []


def take_loan(runner, state, firm_id, amount, bank_id, year, day) -> dict:
    """Nimmt einen angebotenen Investitionskredit auf."""
    try:
        amount = float(amount)
        if amount <= 0:
            return {"ok": False, "message": "Der Kreditbetrag muss grösser als null sein"}

        env = runner.env
        banking = getattr(env, "banking", None)
        if banking is None:
            return {"ok": False, "message": "Keine Banken im Experiment"}

        offers = loan_offers(runner, firm_id, amount)
        if bank_id is None:
            available = [offer for offer in offers if offer["ok"]]
            selected = min(available, key=lambda offer: offer["rate"]) if available else None
        else:
            selected = next((offer for offer in offers if offer["bank_id"] == bank_id), None)

        if selected is None or not selected["ok"]:
            if selected is not None:
                reason = selected["reason"]
            elif offers:
                reason = offers[0]["reason"] or "Kein Angebot"
            else:
                reason = "Keine aktive Bank"
            return {"ok": False, "message": f"Kredit abgelehnt: {reason}"}

        bank = banking.banks[selected["bank_id"]]
        rate = float(selected["rate"])
        years = int(selected["years"])
        banking.grant_loan(
            firm_id,
            env.runtimes[firm_id],
            bank,
            amount,
            rate,
            years,
            "truck",
            year,
            day,
            state.events,
        )
        return {
            "ok": True,
            "message": (
                f"Kredit von {_chf(amount)} bei {bank.name} zu "
                f"{rate * 100:.2f} % über {years} Jahre aufgenommen"
            ),
        }
    except Exception:
        return {"ok": False, "message": "Kredit konnte nicht aufgenommen werden"}


def truck_offers(runner, firm_id) -> list[dict]:
    """Gibt Preise und Eigenschaften der verfügbaren Lastwagen aus."""
    try:
        env = runner.env
        trucks = env.geography.trucks
        offers = []
        for name in sorted(trucks.types):
            truck_type = trucks.types[name]
            offer = trucks._best_offer(env, name, prefer_used=False)
            price = offer[0] if offer is not None else trucks.list_price(env, name)
            offers.append({
                "type": name,
                "label": truck_type.label,
                "capacity": round(float(truck_type.capacity), 2),
                "price": round(float(price), 2),
                "annual_cost": round(float(trucks.annual_cost(env, name)), 2),
                "life_years": round(float(truck_type.life_years), 2),
                "lease_possible": (
                    trucks.leasing is not None and offer is not None and not offer[4]
                ),
            })
        return offers
    except Exception:
        return []


def _firm_for_truck(runner, firm_id):
    try:
        return runner.network.firm(firm_id)
    except Exception:
        pass

    try:
        firms = getattr(runner.env, "firms", None)
        if isinstance(firms, dict):
            return firms.get(firm_id)
        if firms is not None:
            for firm in firms:
                if getattr(firm, "id", None) == firm_id:
                    return firm
    except Exception:
        pass
    return None


def buy_truck(runner, state, firm_id, type_name, mode, year, day) -> dict:
    """Kauft oder least einen Lastwagen beim günstigsten Händler."""
    try:
        env = runner.env
        trucks = env.geography.trucks
        if type_name not in trucks.types:
            return {"ok": False, "message": "Unbekannter Lastwagentyp"}
        if mode not in ("buy", "lease"):
            return {"ok": False, "message": "Unbekannte Kaufart"}

        firm = _firm_for_truck(runner, firm_id)
        if firm is None or not hasattr(firm, "transport_mode"):
            return {"ok": False, "message": "Firma nicht gefunden"}

        offer = trucks._best_offer(env, type_name, prefer_used=False)
        if offer is None:
            return {"ok": False, "message": "Kein Händler hat diesen Lastwagen auf Lager"}

        price, _, _, dealer, used, source = offer
        runtime = env.runtimes[firm_id]
        lease = None

        if mode == "buy":
            if not env.arrange_funding(
                firm_id, price, "truck", trucks.cfg.cash_cover, state
            ):
                return {
                    "ok": False,
                    "message": f"Kasse und Kredit reichen nicht für {_chf(price)}",
                }
            runtime.adjust_cash(-price, "lastwagen_kauf")
        else:
            if trucks.leasing is None or used:
                return {"ok": False, "message": "Leasing nicht möglich"}
            lease = trucks.leasing.offer(
                env,
                firm_id,
                price,
                trucks.types[type_name].life_years,
                _policy_rate(env),
                0.5,
            )
            if lease is None:
                return {"ok": False, "message": "Kein Leasingangebot"}

        truck = trucks._deliver(
            env, dealer, type_name, price, used, source, firm_id
        )
        if lease is not None:
            truck.leased = True
            trucks.leasing.start(env, state, firm_id, truck, dealer, lease)
            trucks._assign_service(
                truck, dealer, int(getattr(lease, "years", 0) or 0)
            )

        trucks.purchases.append({
            "year": year,
            "firm": firm_id,
            "dealer": dealer.id,
            "type": type_name,
            "used": used,
            "price": round(price, 2),
            "age": truck.age,
        })
        label = trucks.types[type_name].label
        trucks._event(
            state,
            firm_id,
            "truck_bought",
            f"{label} {'geleast' if lease is not None else 'gekauft'} "
            f"({'Occasion' if used else 'neu'}) bei {dealer.name}, {_chf(price)}",
        )
        firm.transport_mode = "own"
        return {
            "ok": True,
            "message": (
                f"{label} {'geleast' if lease is not None else 'gekauft'} "
                f"für {_chf(price)}"
            ),
        }
    except Exception:
        return {"ok": False, "message": "Lastwagen konnte nicht gekauft werden"}


class Depot:
    """Aktienbestand und Dividenden der Spielerfirma."""

    def __init__(self) -> None:
        self.shares: dict[str, float] = {}
        self.paid: dict[str, float] = {}
        self._div_idx = 0

    def to_dict(self) -> dict:
        try:
            return {
                "shares": dict(self.shares),
                "paid": dict(self.paid),
                "_div_idx": int(self._div_idx),
            }
        except Exception:
            return {"shares": {}, "paid": {}, "_div_idx": 0}

    @classmethod
    def from_dict(cls, d) -> Depot:
        depot = cls()
        try:
            if isinstance(d, dict):
                depot.shares = {
                    str(key): float(value)
                    for key, value in (d.get("shares") or {}).items()
                }
                depot.paid = {
                    str(key): float(value)
                    for key, value in (d.get("paid") or {}).items()
                }
                depot._div_idx = max(0, int(d.get("_div_idx", 0)))
        except Exception:
            return cls()
        return depot

    @staticmethod
    def _stock_market(runner):
        return getattr(runner, "stock_market", None)

    @staticmethod
    def _name(runner, firm_id: str) -> str:
        try:
            market = getattr(runner, "stock_market", None)
            if market is not None and hasattr(market, "_name"):
                return market._name(runner, firm_id)
        except Exception:
            pass
        return firm_id

    @staticmethod
    def _fee_rate(runner) -> float:
        try:
            holdings = getattr(runner, "holdings", None)
            if holdings is not None:
                return float(holdings.cfg.broker_fee)
        except Exception:
            pass
        return 0.005

    def buy(self, runner, firm_id_owner, target_id, shares) -> dict:
        """Kauft Aktien und verbucht Kaufpreis sowie Gebühr."""
        try:
            shares = float(shares)
            if shares <= 0:
                return {"ok": False, "message": "Die Aktienmenge muss grösser als null sein"}
            if target_id == firm_id_owner:
                return {"ok": False, "message": "Eigene Aktien kann man nicht kaufen"}

            market = self._stock_market(runner)
            if market is None:
                return {"ok": False, "message": "Keine Börse"}
            name = self._name(runner, target_id)
            price = market.price(target_id)
            if price is None:
                return {"ok": False, "message": f"{name} ist nicht börsenkotiert"}

            available = float(market.cfg.shares_per_firm) - self.shares.get(target_id, 0.0)
            if shares > available:
                return {"ok": False, "message": "Nicht genügend Aktien verfügbar"}

            cost = shares * float(price)
            fee = cost * self._fee_rate(runner)
            total = cost + fee
            runtime = runner.env.runtimes[firm_id_owner]
            can_spend = getattr(runner.env, "can_spend", None)
            enough_cash = (
                can_spend(firm_id_owner, total)
                if callable(can_spend)
                else runtime.cash >= total
            )
            if not enough_cash:
                return {"ok": False, "message": "Nicht genug Kasse"}

            runtime.adjust_cash(-total, "aktien_kauf")
            self.shares[target_id] = self.shares.get(target_id, 0.0) + shares
            self.paid[target_id] = self.paid.get(target_id, 0.0) + total

            banking = getattr(runner.env, "banking", None)
            if banking is not None and banking.accounts.get(firm_id_owner):
                banking.primary_bank(firm_id_owner).fee_income += fee

            return {
                "ok": True,
                "message": f"{shares:g} Aktien von {name} für {_chf(total)} gekauft",
                "cost": total,
            }
        except Exception:
            return {"ok": False, "message": "Aktien konnten nicht gekauft werden"}

    def sell(self, runner, firm_id_owner, target_id, shares) -> dict:
        """Verkauft Aktien und zahlt den Erlös nach Gebühren aus."""
        try:
            shares = float(shares)
            if shares <= 0:
                return {"ok": False, "message": "Die Aktienmenge muss grösser als null sein"}
            held = self.shares.get(target_id, 0.0)
            if shares > held:
                return {"ok": False, "message": "Nicht genug Aktien im Depot"}

            market = self._stock_market(runner)
            if market is None:
                return {"ok": False, "message": "Keine Börse"}
            name = self._name(runner, target_id)
            price = market.price(target_id)
            if price is None:
                return {"ok": False, "message": f"{name} ist nicht börsenkotiert"}

            proceeds = shares * float(price)
            fee = proceeds * self._fee_rate(runner)
            net = proceeds - fee
            runtime = runner.env.runtimes[firm_id_owner]
            runtime.adjust_cash(net, "aktien_verkauf")

            remaining = held - shares
            if remaining <= 0:
                self.shares.pop(target_id, None)
                self.paid.pop(target_id, None)
            else:
                self.shares[target_id] = remaining
                self.paid[target_id] = self.paid.get(target_id, 0.0) * (
                    1.0 - shares / held
                )

            banking = getattr(runner.env, "banking", None)
            if banking is not None and banking.accounts.get(firm_id_owner):
                banking.primary_bank(firm_id_owner).fee_income += fee

            return {
                "ok": True,
                "message": f"{shares:g} Aktien von {name} für {_chf(net)} verkauft",
                "cost": net,
            }
        except Exception:
            return {"ok": False, "message": "Aktien konnten nicht verkauft werden"}

    def positions(self, runner) -> list[dict]:
        """Gibt die gehaltenen Aktienpositionen samt aktuellem Wert zurück."""
        try:
            market = self._stock_market(runner)
            if market is None:
                return []
            positions = []
            for firm_id in sorted(self.shares):
                shares = float(self.shares[firm_id])
                price = market.price(firm_id)
                price = float(price) if price is not None else 0.0
                paid = float(self.paid.get(firm_id, 0.0))
                value = shares * price
                positions.append({
                    "id": firm_id,
                    "name": self._name(runner, firm_id),
                    "shares": shares,
                    "price": price,
                    "value": value,
                    "paid": paid,
                    "gain": value - paid,
                })
            return positions
        except Exception:
            return []

    def pay_dividends(self, runner, state, owner_id) -> float:
        """Verarbeitet neue Dividenden aus dem Aktienbestand."""
        try:
            distribution = getattr(runner, "profit_distribution", None)
            if distribution is None:
                return 0.0
            history = getattr(distribution, "history", None)
            if not history:
                self._div_idx = 0
                return 0.0

            start = max(0, min(self._div_idx, len(history)))
            market = self._stock_market(runner)
            shares_per_firm = (
                float(market.cfg.shares_per_firm) if market is not None else 0.0
            )
            amount = 0.0
            if shares_per_firm > 0:
                for row in history[start:]:
                    firm_id = row.get("firm")
                    if firm_id in self.shares:
                        amount += (
                            self.shares[firm_id]
                            / shares_per_firm
                            * float(row.get("net_dividend", 0.0))
                        )
            self._div_idx = len(history)

            if amount > 0:
                runner.env.runtimes[owner_id].adjust_cash(
                    amount, "dividende:aktien"
                )
                state.events.append({
                    "year": state.year,
                    "day": 0,
                    "firm": owner_id,
                    "event": "dividend_received",
                    "details": f"Dividenden aus Aktien: {_chf(amount)}",
                })
            return float(amount)
        except Exception:
            return 0.0
