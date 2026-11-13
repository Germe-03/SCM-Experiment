"""Spielmodus Feedback 6 (B): Lieferverträge (Deals) zwischen Spieler- und KI-Firmen.

Mengen sind intern in Sim-Einheiten (``units_per_day``); der Preis ist CHF pro Flasche.
Ohne aktive Verträge ändert dieses Modul nichts am Marktverlauf. Alle Zufälle kommen aus
einem eigenen ``random.Random`` und nie aus bestehenden Strömen.
"""
from __future__ import annotations

import random
from collections import deque

# Lieferant (Stufe) -> erlaubte Kundenstufe.
ALLOWED_STAGES = {"factory": "distributor", "distributor": "wholesaler", "wholesaler": "retailer"}
STATUS_OFFERED, STATUS_ACTIVE, STATUS_DECLINED, STATUS_ENDED = "angeboten", "aktiv", "abgelehnt", "beendet"


class ContractBook:
    """Alle Verträge eines Laufs. ``runner`` liefert Netzwerk, Umgebung und Spielerfirmen."""

    def __init__(self, runner) -> None:
        self.runner = runner
        self.contracts: list[dict] = []
        self._next_id = 1
        self.rng = random.Random(int(getattr(runner, "seed", 0)) * 7919 + 4711)
        self._active: list[dict] = []
        self.change_rng = random.Random(int(getattr(runner, "seed", 0)) * 6271 + 1337)
        self._demand: dict[str, deque] = {}

    # --- Zugriff -----------------------------------------------------------------------------
    @property
    def env(self):
        return self.runner.env

    @property
    def has_active(self) -> bool:
        return bool(self._active)

    def _unit_size(self) -> int:
        return int(self.runner.config.unit_scale.real_units_per_sim_unit)

    def _now(self) -> int:
        return int(self.env.period)

    def _is_player(self, firm_id: str) -> bool:
        return firm_id in self.runner.player_choices

    def get(self, contract_id: int) -> dict:
        for contract in self.contracts:
            if contract["id"] == int(contract_id):
                return contract
        raise KeyError(f"Unbekannter Vertrag: {contract_id}")

    def _refresh(self) -> None:
        now = self._now()
        runtimes = self.env.runtimes
        for contract in self.contracts:
            # Konkurs oder Schliessung einer Seite: Der Vertrag endet sofort (keine Lieferung, keine Strafe);
            # offene Angebote mit einer geschlossenen Firma verfallen.
            gone = [side for side in ("supplier", "buyer")
                    if runtimes.get(contract[side]) is None or not runtimes[contract[side]].active]
            if gone and contract["status"] in (STATUS_ACTIVE, STATUS_OFFERED):
                contract["status"] = STATUS_ENDED if contract["status"] == STATUS_ACTIVE else STATUS_DECLINED
                contract["end_reason"] = "Konkurs/Schliessung: " + ", ".join(contract[side] for side in gone)
                contract["end_day"] = now
                continue
            if contract["status"] == STATUS_ACTIVE and now >= contract["start_day"] + contract["days"]:
                contract["status"] = STATUS_ENDED
                contract["end_reason"] = "Laufzeit abgelaufen"
        self._active = [c for c in self.contracts if c["status"] == STATUS_ACTIVE]

    def _in_window(self, contract: dict, now: int) -> bool:
        return contract["start_day"] <= now < contract["start_day"] + contract["days"]

    def active_for(self, firm_id: str) -> list[dict]:
        """Aktive Verträge, in denen die Firma Lieferant oder Kunde ist."""
        self._refresh()
        return [c for c in self._active if firm_id in (c["supplier"], c["buyer"])]

    def offers_for(self, firm_id: str) -> list[dict]:
        """Offene Angebote an die Firma (nicht von ihr selbst gemacht)."""
        return [c for c in self.contracts if c["status"] == STATUS_OFFERED
                and firm_id in (c["supplier"], c["buyer"]) and c["proposed_by"] != firm_id]

    def proposed_by(self, firm_id: str) -> list[dict]:
        return [c for c in self.contracts if c["status"] == STATUS_OFFERED and c["proposed_by"] == firm_id]

    def partners(self, firm_id: str) -> list[dict]:
        """Mögliche Vertragspartner: {"id","name","stage","role","market_price"}; role = Rolle des Partners."""
        result = []
        for other in self.runner._firms():
            runtime = self.env.runtimes.get(other.id)
            if runtime is None or not runtime.active:
                continue
            if self.pair_error(firm_id, other.id) is None:
                role = "Kunde"
            elif self.pair_error(other.id, firm_id) is None:
                role = "Lieferant"
            else:
                continue
            result.append({"id": other.id, "name": other.name, "stage": other.stage, "role": role,
                           "market_price": float(other.sell_price)})
        return sorted(result, key=lambda item: (item["stage"], item["id"]))

    def pair_error(self, supplier_id: str, buyer_id: str) -> str | None:
        """None, wenn das Paar erlaubt ist, sonst ein deutscher Grund."""
        network = self.runner.network
        try:
            supplier, buyer = network.firm(supplier_id), network.firm(buyer_id)
        except (KeyError, ValueError):
            return "Unbekannte Firma"
        if ALLOWED_STAGES.get(supplier.stage) != buyer.stage:
            return "Dieses Paar darf keinen Liefervertrag schliessen"
        return None

    # --- Aufträge ----------------------------------------------------------------------------
    def propose(self, supplier: str, buyer: str, units_per_day: float, price: float, days: int,
                category: str | None = None, proposed_by: str | None = None,
                start_day: int | None = None) -> dict:
        """Neues Angebot (Menge in Sim-Einheiten pro Tag). Wirft ValueError bei ungültigen Angaben."""
        reason = self.pair_error(supplier, buyer)
        if reason:
            raise ValueError(reason)
        units_per_day, price, days = float(units_per_day), float(price), int(days)
        if units_per_day <= 0 or price <= 0 or days <= 0:
            raise ValueError("Menge, Preis und Laufzeit müssen positiv sein")
        proposer = proposed_by or supplier
        if proposer not in (supplier, buyer):
            raise ValueError("Der Vorschlagende muss Lieferant oder Kunde sein")
        for contract in self.contracts:
            if (contract["status"] in (STATUS_OFFERED, STATUS_ACTIVE) and contract["supplier"] == supplier
                    and contract["buyer"] == buyer and contract["category"] == category):
                raise ValueError("Für dieses Paar gibt es schon einen offenen oder aktiven Vertrag")
        contract = {
            "id": self._next_id, "supplier": supplier, "buyer": buyer, "category": category,
            "units_per_day": units_per_day, "price": price,
            "start_day": self._now() if start_day is None else int(start_day), "days": days,
            "status": STATUS_OFFERED, "proposed_by": proposer,
            "ordered": 0.0, "delivered": 0.0, "change": None,
        }
        self._next_id += 1
        self.contracts.append(contract)
        return contract

    def propose_bottles(self, supplier: str, buyer: str, bottles_per_day: float, price: float, days: int,
                        category: str | None = None, proposed_by: str | None = None) -> dict:
        return self.propose(supplier, buyer, float(bottles_per_day) / self._unit_size(), price, days,
                            category, proposed_by)

    def accept(self, contract_id: int) -> dict:
        contract = self.get(contract_id)
        if contract["status"] != STATUS_OFFERED:
            raise ValueError("Nur Angebote können angenommen werden")
        contract["status"] = STATUS_ACTIVE
        contract["start_day"] = self._now()
        self._refresh()
        return contract

    def decline(self, contract_id: int) -> dict:
        contract = self.get(contract_id)
        if contract["status"] != STATUS_OFFERED:
            raise ValueError("Nur Angebote können abgelehnt werden")
        contract["status"] = STATUS_DECLINED
        return contract

    def cancel(self, contract_id: int) -> dict:
        """Beendet einen aktiven Vertrag; ein offenes Angebot wird zurückgezogen (abgelehnt)."""
        contract = self.get(contract_id)
        if contract["status"] == STATUS_ACTIVE:
            contract["status"] = STATUS_ENDED
        elif contract["status"] == STATUS_OFFERED:
            contract["status"] = STATUS_DECLINED
        else:
            raise ValueError("Der Vertrag läuft nicht mehr")
        self._refresh()
        return contract

    # --- Vertragsanpassungen -----------------------------------------------------------------
    def propose_change(self, contract_id: int, proposed_by: str, units_per_day: float | None = None,
                       price: float | None = None) -> dict:
        """Änderungsvorschlag (Menge in Sim-Einheiten/Tag und/oder Preis) für einen aktiven Vertrag."""
        contract = self.get(contract_id)
        if contract["status"] != STATUS_ACTIVE:
            raise ValueError("Nur aktive Verträge können angepasst werden")
        if proposed_by not in (contract["supplier"], contract["buyer"]):
            raise ValueError("Der Vorschlagende muss Lieferant oder Kunde sein")
        if units_per_day is None and price is None:
            raise ValueError("Menge oder Preis muss angegeben werden")
        units = contract["units_per_day"] if units_per_day is None else float(units_per_day)
        new_price = contract["price"] if price is None else float(price)
        if units <= 0 or new_price <= 0:
            raise ValueError("Menge und Preis müssen positiv sein")
        if units == contract["units_per_day"] and new_price == contract["price"]:
            raise ValueError("Die Änderung entspricht dem bestehenden Vertrag")
        contract["change"] = {"units_per_day": units, "price": new_price,
                              "proposed_by": proposed_by, "day": self._now()}
        contract["change_result"] = None
        return contract

    def propose_change_bottles(self, contract_id: int, proposed_by: str, bottles_per_day: float | None = None,
                               price: float | None = None) -> dict:
        units = None if bottles_per_day is None else float(bottles_per_day) / self._unit_size()
        return self.propose_change(contract_id, proposed_by, units, price)

    def accept_change(self, contract_id: int) -> dict:
        contract = self.get(contract_id)
        change = contract.get("change")
        if contract["status"] != STATUS_ACTIVE or not change:
            raise ValueError("Es gibt keine offene Änderung")
        contract["units_per_day"] = float(change["units_per_day"])
        contract["price"] = float(change["price"])
        contract["change_result"] = {"status": "angenommen", "proposed_by": change["proposed_by"],
                                     "day": self._now()}
        contract["change"] = None
        return contract

    def decline_change(self, contract_id: int) -> dict:
        contract = self.get(contract_id)
        change = contract.get("change")
        if contract["status"] != STATUS_ACTIVE or not change:
            raise ValueError("Es gibt keine offene Änderung")
        contract["change_result"] = {"status": "abgelehnt", "proposed_by": change["proposed_by"],
                                     "day": self._now()}
        contract["change"] = None
        return contract

    def view(self, contract: dict) -> dict:
        """Kopie mit Mengen in Flaschen (units_per_day, ordered, delivered) und Unterlieferung."""
        size = self._unit_size()
        out = dict(contract)
        for key in ("units_per_day", "ordered", "delivered"):
            out[key] = contract[key] * size
        out["shortfall"] = max(0.0, out["ordered"] - out["delivered"])
        return out

    # --- Wirkung im Markt (von environment.step aufgerufen) -----------------------------------
    def _pair_contracts(self, supplier: str, buyer: str, now: int) -> list[dict]:
        return [c for c in self._active if c["supplier"] == supplier and c["buyer"] == buyer
                and self._in_window(c, now)]

    def buyer_orders(self, buyer_id: str, quantity: int, now: int) -> dict[str, int]:
        """Vertragsmengen, die vom Auftrag des Kunden zuerst an die Vertragslieferanten gehen."""
        # Ein Vertrag ist verbindlich: Der Kunde bestellt die Vertragsmenge jeden Tag, auch wenn er
        # selbst weniger bräuchte (sonst wäre der Vertrag nur eine unverbindliche Absicht).
        result: dict[str, int] = {}
        runtimes = self.env.runtimes
        self._demand.setdefault(buyer_id, deque(maxlen=30)).append(float(quantity))
        for contract in sorted(self._active, key=lambda c: c["id"]):
            if contract["buyer"] != buyer_id or not self._in_window(contract, now):
                continue
            supplier = runtimes.get(contract["supplier"])
            if supplier is None or not supplier.active:
                continue
            units = int(round(contract["units_per_day"]))
            if units <= 0:
                continue
            result[contract["supplier"]] = result.get(contract["supplier"], 0) + units
            contract["ordered"] += units
        return result

    def supplier_priority(self, supplier_id: str, requested: dict[str, int], now: int) -> dict[str, int]:
        """Je Vertragskunde die Menge, die der Lieferant zuerst bedient (höchstens Vertragsmenge/Tag)."""
        result: dict[str, int] = {}
        for contract in self._active:
            if contract["supplier"] != supplier_id or not self._in_window(contract, now):
                continue
            if requested.get(contract["buyer"], 0) > 0:
                result[contract["buyer"]] = result.get(contract["buyer"], 0) + int(round(contract["units_per_day"]))
        return {buyer: min(units, requested[buyer]) for buyer, units in result.items() if units > 0}

    def price_for(self, supplier_id: str, buyer_id: str, units: int, contract_units: int,
                  market_price: float, now: int) -> float:
        """Mischpreis (CHF/Flasche): contract_units zum Vertragspreis, der Rest zum Marktpreis."""
        pair = self._pair_contracts(supplier_id, buyer_id, now)
        if not pair or units <= 0 or contract_units <= 0:
            return market_price
        contract_units = min(contract_units, units)
        total = sum(c["units_per_day"] for c in pair)
        contract_price = sum(c["price"] * c["units_per_day"] for c in pair) / total
        return (contract_units * contract_price + (units - contract_units) * market_price) / units

    def record_delivery(self, supplier_id: str, buyer_id: str, contract_units: int, now: int) -> None:
        """Verbucht gelieferte Vertragsmenge (Rest zu ordered ist Unterlieferung)."""
        left = float(contract_units)
        for contract in sorted(self._pair_contracts(supplier_id, buyer_id, now), key=lambda c: c["id"]):
            if left <= 0:
                break
            part = min(left, contract["units_per_day"])
            contract["delivered"] += part
            left -= part

    # --- KI-Entscheide (täglich/vierteljährlich vom Runner aufgerufen) -----------------------
    def daily(self) -> None:
        self._refresh()
        self._decide_player_proposals()
        self._decide_player_changes()
        days = self.runner.config.simulation.days_per_year
        quarter = max(1, days // 4)
        now = self._now()
        if now > 0 and now % quarter == 0:
            self._make_ai_offers()
            self._make_ai_changes()
        self._refresh()

    def _market_price(self, firm_id: str, as_supplier: bool, partner_id: str) -> float:
        network = self.runner.network
        if as_supplier:
            return float(network.firm(firm_id).sell_price)
        # Kunde: Marktpreis = Durchschnitt der Verkaufspreise seiner möglichen Lieferanten
        stage = network.firm(firm_id).stage
        prices = [float(f.sell_price) for f in self.runner._firms()
                  if ALLOWED_STAGES.get(f.stage) == stage and self.env.runtimes[f.id].active]
        return sum(prices) / len(prices) if prices else float(network.firm(partner_id).sell_price)

    def _decide_player_proposals(self) -> None:
        cfg = self.runner.config.contracts
        for contract in self.contracts:
            if contract["status"] != STATUS_OFFERED or not self._is_player(contract["proposed_by"]):
                continue
            ai_id = contract["buyer"] if contract["proposed_by"] == contract["supplier"] else contract["supplier"]
            if self._is_player(ai_id):
                continue  # Spieler-Spieler: Gegenseite entscheidet selbst
            runtime = self.env.runtimes.get(ai_id)
            if runtime is None or not runtime.active:
                contract["status"] = STATUS_DECLINED
                continue
            ai_is_supplier = ai_id == contract["supplier"]
            market = self._market_price(ai_id, ai_is_supplier, contract["proposed_by"])
            if ai_is_supplier:
                price_ok = contract["price"] >= market * (1 - cfg.price_tolerance)
            else:
                price_ok = contract["price"] <= market * (1 + cfg.price_tolerance)
            capacity = self.env._effective_capacity(ai_id)
            qty_ok = contract["units_per_day"] <= cfg.max_capacity_share * capacity
            if price_ok and qty_ok:
                contract["status"] = STATUS_ACTIVE
                contract["start_day"] = self._now()
            else:
                contract["status"] = STATUS_DECLINED

    def _ai_accepts(self, contract: dict, ai_id: str, units: float, price: float, other_id: str) -> bool:
        cfg = self.runner.config.contracts
        ai_is_supplier = ai_id == contract["supplier"]
        market = self._market_price(ai_id, ai_is_supplier, other_id)
        if ai_is_supplier:
            price_ok = price >= market * (1 - cfg.price_tolerance)
        else:
            price_ok = price <= market * (1 + cfg.price_tolerance)
        qty_ok = units <= cfg.max_capacity_share * self.env._effective_capacity(ai_id)
        return price_ok and qty_ok

    def _decide_player_changes(self) -> None:
        """KI entscheidet über Änderungsvorschläge der Spieler (wie bei neuen Verträgen)."""
        for contract in self.contracts:
            change = contract.get("change")
            if contract["status"] != STATUS_ACTIVE or not change or not self._is_player(change["proposed_by"]):
                continue
            ai_id = contract["buyer"] if change["proposed_by"] == contract["supplier"] else contract["supplier"]
            if self._is_player(ai_id):
                continue
            runtime = self.env.runtimes.get(ai_id)
            if runtime is None or not runtime.active:
                continue
            if self._ai_accepts(contract, ai_id, change["units_per_day"], change["price"], change["proposed_by"]):
                self.accept_change(contract["id"])
            else:
                self.decline_change(contract["id"])

    def _make_ai_changes(self) -> None:
        """KI schlägt (einmal pro Quartal) Anpassungen an Verträgen mit Spielern vor."""
        for contract in sorted(self._active, key=lambda c: c["id"]):
            if contract.get("change"):
                continue
            supplier_player, buyer_player = self._is_player(contract["supplier"]), self._is_player(contract["buyer"])
            if supplier_player == buyer_player:
                continue  # nur Verträge zwischen KI und Spieler
            ai_id = contract["buyer"] if supplier_player else contract["supplier"]
            ai_is_buyer = ai_id == contract["buyer"]
            runtime = self.env.runtimes.get(ai_id)
            if runtime is None or not runtime.active:
                continue
            units, price = contract["units_per_day"], contract["price"]
            new_units, new_price = units, price
            history = self._demand.get(ai_id)
            if ai_is_buyer and history:
                need = sum(history) / len(history)
                if need > 0 and (need < units * 0.7 or need > units * 1.3):
                    new_units = max(1.0, float(round(need)))
            other = contract["supplier"] if ai_is_buyer else contract["buyer"]
            market = self._market_price(ai_id, not ai_is_buyer, other)
            if market > 0 and abs(market - price) / market > 0.05:
                new_price = round(price + (market - price) * 0.5, 4)
            if (new_units, new_price) == (units, price):
                continue
            contract["change"] = {"units_per_day": new_units, "price": new_price,
                                  "proposed_by": ai_id, "day": self._now()}

    def _make_ai_offers(self) -> None:
        cfg = self.runner.config.contracts
        if cfg.offers_per_quarter <= 0:
            return
        network = self.runner.network
        runtimes = self.env.runtimes
        candidates: list[tuple[str, str, str]] = []  # (Lieferant, Kunde, KI-Firma)
        for player_id in sorted(self.runner.player_choices):
            runtime = runtimes.get(player_id)
            if runtime is None or not runtime.active:
                continue
            for other in sorted(self.runner._firms(), key=lambda f: f.id):
                other_rt = runtimes.get(other.id)
                if other.id == player_id or self._is_player(other.id) or other_rt is None or not other_rt.active:
                    continue
                if self.pair_error(player_id, other.id) is None:
                    candidates.append((player_id, other.id, other.id))
                elif self.pair_error(other.id, player_id) is None:
                    candidates.append((other.id, player_id, other.id))
        self.rng.shuffle(candidates)
        made = 0
        for supplier, buyer, ai_id in candidates:
            if made >= cfg.offers_per_quarter:
                break
            if self.rng.random() >= cfg.offer_probability:
                continue
            if any(c["status"] in (STATUS_OFFERED, STATUS_ACTIVE) and c["supplier"] == supplier
                   and c["buyer"] == buyer for c in self.contracts):
                continue
            ai_is_supplier = ai_id == supplier
            market = self._market_price(ai_id, ai_is_supplier, buyer if ai_is_supplier else supplier)
            capacity = self.env._effective_capacity(ai_id)
            units = max(1.0, round(cfg.offer_capacity_share * capacity))
            price = market * (1 - cfg.offer_discount) if ai_is_supplier else market
            if price <= 0:
                continue
            self.propose(supplier, buyer, units, round(price, 4), cfg.offer_days, proposed_by=ai_id)
            made += 1
