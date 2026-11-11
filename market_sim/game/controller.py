from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import datetime
from pathlib import Path
import re
import threading

from market_sim.game.choices import PlayerChoices
from market_sim.game.change_log import describe_changes
from market_sim.game.messages import messages_for
from market_sim.game.player import PlayerSettings
from market_sim.game.saves import SaveGame, list_saves, read_save, replay, write_save
from market_sim.game.session import BRANCHES, GameSession, RoundSnapshot


ROHSTOFFE_DE = {
    "co2": "CO2", "cork": "Kork", "fruit": "Früchte", "grapes": "Trauben", "hops": "Hopfen",
    "malt": "Malz", "packaging": "Verpackung", "glass": "Glas", "sugar": "Zucker",
    "water": "Wasser", "wheat": "Weizen", "barley": "Gerste", "electricity": "Strom",
    "energy": "Energie", "aluminium": "Aluminium", "pet": "PET", "yeast": "Hefe",
    "grain": "Getreide", "potatoes": "Kartoffeln", "wood": "Holz", "labels": "Etiketten",
}
STUFEN_DE = {"factory": "Hersteller", "wholesaler": "Grosshändler", "distributor": "Verteiler",
             "retailer": "Detailhandel"}


def _german_view(name: str, data: dict) -> dict:
    """Englische Schlüssel der Simulation für die Anzeige übersetzen."""
    if name == "commodities" and isinstance(data, dict):
        for row in data.get("current", []):
            row["name"] = ROHSTOFFE_DE.get(row.get("name"), row.get("name"))
            if isinstance(row.get("index"), (int, float)):
                row["index"] = round(row["index"] * 100, 1)
        data["history"] = [{ROHSTOFFE_DE.get(k, k): (round(v * 100, 1) if k not in
                            ("label", "policy_rate", "inflation", "fx_rate") and isinstance(v, (int, float)) else v)
                            for k, v in row.items()} for row in data.get("history", [])]
    if name == "swiss_map" and isinstance(data, dict):
        for firm in data.get("firms", []):
            firm["stage"] = STUFEN_DE.get(firm.get("stage"), firm.get("stage"))
    return data


class GameController:
    """Steuert Spielrunden, Meldungen und Spielstände."""

    _BRANCH_LABELS = {
        "hersteller": "Hersteller",
        "grosshaendler": "Grosshändler",
        "verteiler": "Verteiler",
        "detailhaendler": "Detailhändler",
        "gastro": "Gastronomie",
    }

    def __init__(
        self,
        save_dir: Path,
        seed: int = 0,
        years: int | None = None,
        days_per_year: int | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.save_dir = Path(save_dir)
        self.seed = seed
        self.years = years
        self.days_per_year = days_per_year
        self.session: GameSession | None = None
        self.snapshot: RoundSnapshot | None = None
        self.protocol: SaveGame | None = None
        self.history: list[dict] = []
        self.messages: list[dict] = []
        self.macro_history: list[dict] = []
        self.effects: list[dict] = []
        self._pending_changes: list[str] = []
        self.sale: dict | None = None
        self._options_cache: dict | None = None

    def options(self) -> dict:
        """Gibt Branchen, Regionen und Kategorien zurück."""
        with self._lock:
            if self._options_cache is not None:
                return {**self._options_cache, "research": self._research_options()}

            regions = []
            categories = []
            banks = []
            offences = []
            try:
                session = GameSession(self.seed, self.years, self.days_per_year)
                config = session.runner.config
                geography = getattr(config, "geography", None)
                if geography is not None and getattr(geography, "enabled", False):
                    regions = [region.name for region in geography.regions]

                banking = getattr(session.runner.env, "banking", None)
                if banking is not None:
                    banks = [
                        {"id": bank.id, "name": bank.name}
                        for bank in banking.banks.values()
                    ]
                offences = [
                    {
                        "name": item.name,
                        "benefit": float(item.benefit),
                        "fine": float(item.fine_fixed),
                    }
                    for item in getattr(getattr(config, "state", None), "offences", [])
                ]

                category_config = getattr(config, "categories", None)
                if category_config is not None:
                    categories = [
                        category.name for category in category_config.categories
                    ]
            except Exception:
                regions = []
                categories = []
                banks = []
                offences = []

            self._options_cache = {
                "branches": [
                    {"key": key, "label": self._BRANCH_LABELS[key]}
                    for key in BRANCHES
                ],
                "regions": regions,
                "categories": categories,
                "banks": banks,
                "offences": offences,
            }
            return {**self._options_cache, "research": self._research_options()}

    def new_game(
        self,
        branch: str,
        name: str,
        region: str | None = None,
        category: str | None = None,
    ) -> dict:
        """Gründet eine Firma und startet ein neues Spiel."""
        with self._lock:
            try:
                session = GameSession(self.seed, self.years, self.days_per_year)
                session.found(branch, name, region, category)
                snapshot = session.start()
                protocol = SaveGame(
                    seed=self.seed,
                    years=self.years,
                    days_per_year=self.days_per_year,
                    branch=branch,
                    name=name,
                    region=region,
                    category=category,
                    rounds=[],
                )

                self.session = session
                self.snapshot = snapshot
                self.protocol = protocol
                self.history = []
                self.messages = []
                self.macro_history = []
                self.effects = []
                self._pending_changes = []
                self.sale = None
                self._process(snapshot)
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def end_round(self, settings: dict | None = None, choices: dict | None = None,
                  orders: dict | None = None) -> dict:
        """Übernimmt Einstellungen und beendet die aktuelle Runde."""
        with self._lock:
            try:
                if self.session is None or self.snapshot is None:
                    raise RuntimeError("Kein Spiel aktiv")
                if self.session.finished or self.snapshot.game_over:
                    raise RuntimeError("Das Spiel ist bereits beendet")

                current = self.snapshot.settings
                updates = {}
                allowed = {item.name for item in fields(PlayerSettings)}
                for key, value in (settings or {}).items():
                    if key not in allowed:
                        raise ValueError(f"Unbekannte Einstellung: {key}")
                    try:
                        if key in {
                            "base_price",
                            "overtime_level",
                            "wage_level",
                            "r_and_d_budget",
                            "target_quality",
                            "risk_tolerance",
                        }:
                            updates[key] = float(value)
                        elif key in {"target_safety_stock_days", "hiring_plan"}:
                            updates[key] = int(value)
                        elif key == "order_qty":
                            updates[key] = (
                                None
                                if value is None or str(value).strip() == ""
                                else int(value)
                            )
                        else:
                            updates[key] = str(value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"Ungültige Einstellung: {key}") from exc

                new_settings = replace(current, **updates)
                self._pending_changes = describe_changes(current, updates, choices or {}, orders or {})
                snapshot = self.session.end_round(new_settings, choices or None, orders or None)
                if self.protocol is not None:
                    # Alte Spielstände ohne "choices": auf gleiche Länge auffüllen.
                    while len(self.protocol.choices) < len(self.protocol.rounds):
                        self.protocol.choices.append({})
                    self.protocol.rounds.append(asdict(new_settings))
                    self.protocol.choices.append(dict(choices or {}))
                    while len(self.protocol.orders) < len(self.protocol.rounds) - 1:
                        self.protocol.orders.append({})
                    self.protocol.orders.append(dict(orders or {}))
                self.snapshot = snapshot
                self._process(snapshot)
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def sell(self) -> dict:
        """Verkauft die Firma und beendet das Spiel."""
        with self._lock:
            try:
                if self.session is None:
                    raise RuntimeError("Kein Spiel aktiv")

                event_mark = self.session._event_mark
                result = self.session.sell_firm()
                self.sale = {
                    "price": float(result.price),
                    "year": int(result.year),
                    "month": int(result.month),
                }
                self.session._event_mark = event_mark
                snapshot = self.session._snapshot(
                    self.session.runner,
                    self.session._state,
                    self.session._last_year,
                    self.session._last_day,
                    game_over=True,
                    reason="verkauft",
                )
                self.snapshot = snapshot
                self._process(snapshot)
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def save(self, name: str) -> dict:
        """Speichert das aktuelle Spiel unter einem bereinigten Namen."""
        with self._lock:
            try:
                name = self._clean_name(name)
                if not name:
                    raise ValueError("Ungültiger Name")
                if self.session is None or self.snapshot is None:
                    raise RuntimeError("Kein Spiel aktiv")
                if self.snapshot.game_over:
                    raise RuntimeError("Beendete Spiele können nicht gespeichert werden")
                if self.protocol is None:
                    raise RuntimeError("Kein Spiel aktiv")

                save = replace(
                    self.protocol,
                    saved_at=datetime.now().isoformat(timespec="seconds"),
                    label=f"Jahr {self.snapshot.year}, Monat {self.snapshot.month}",
                )
                write_save(save, self.save_dir / f"{name}.json")
                return {"ok": True, "name": name}
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def load(self, name: str) -> dict:
        """Lädt einen Spielstand und spielt seine Runden erneut ab."""
        with self._lock:
            try:
                name = self._clean_name(name)
                if not name:
                    raise ValueError("Ungültiger Name")

                path = self.save_dir / f"{name}.json"
                if not path.exists():
                    raise ValueError("Spielstand nicht gefunden")

                save = read_save(path)
                snapshots = []
                session, snapshot = replay(save, snapshots.append)

                self.session = session
                self.snapshot = snapshot
                self.protocol = save
                self.history = []
                self.messages = []
                self.macro_history = []
                self.effects = []
                self._pending_changes = []
                self.sale = None
                for item in snapshots:
                    self._process(item)
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def advise(self, question: str | None = None, llm=None) -> dict:
        """Fragt den Berater (Sprachmodell) nach Tipps; nur eigene und öffentliche Daten."""
        from market_sim.game.advisor import advise
        state = self.state()
        if llm is None:
            if getattr(self, "_llm", None) is None:
                from market_sim.config import load_market_config
                from market_sim.llm import make_client
                self._llm = make_client(load_market_config().ollama, chat=True)
            llm = self._llm
        # Das Sprachmodell wird ausserhalb der Sperre gefragt: das Spiel bleibt bedienbar.
        return advise(llm, state, (question or "").strip()[:500] or None)

    def saves(self) -> dict:
        """Listet die gespeicherten Spiele auf."""
        with self._lock:
            try:
                return {"saves": list_saves(self.save_dir)}
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def state(self) -> dict:
        """Gibt den aktuellen Spielzustand zurück."""
        with self._lock:
            try:
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def _process(self, snapshot: RoundSnapshot) -> None:
        """Übernimmt Verlauf und Meldungen eines Snapshots."""
        if not self.history:
            self._start_price = float(snapshot.settings.base_price)
        self.history.append(
            {
                "year": int(snapshot.year),
                "month": int(snapshot.month),
                "cash": float(snapshot.cash),
                "profit": float(snapshot.profit),
                "sell_price": float(snapshot.sell_price),
                "sales": float(snapshot.recent_sales),
                "demand": float(snapshot.recent_demand),
                "inventory": int(snapshot.inventory),
                "backlog": int(snapshot.backlog),
            }
        )
        if self.session is None:
            return
        self._record_macro(snapshot)
        self._record_effect()
        names = {
            firm.id: firm.name
            for firm in self.session.runner._firms()
        }
        self.messages.extend(
            messages_for(snapshot.events, snapshot.firm_id, names)
        )

    def _state(self) -> dict:
        """Baut das JSON für den aktuellen Spielzustand."""
        if self.session is None or self.snapshot is None or self.protocol is None:
            return {"running": False}

        snapshot = self.snapshot
        stage = BRANCHES[self.protocol.branch][0]
        band = self.session.runner.config.stage_prices[stage]
        return {
            "running": True,
            "game_over": bool(snapshot.game_over),
            "reason": snapshot.reason,
            "year": int(snapshot.year),
            "month": int(snapshot.month),
            "firm": {
                "id": snapshot.firm_id,
                "name": snapshot.name,
                "branch": self.protocol.branch,
            },
            "kpis": {
                "cash": float(snapshot.cash),
                "inventory": int(snapshot.inventory),
                "backlog": int(snapshot.backlog),
                "employees": int(snapshot.employees),
                "sell_price": float(snapshot.sell_price),
                "profit": float(snapshot.profit),
                "recent_demand": float(snapshot.recent_demand),
                "recent_sales": float(snapshot.recent_sales),
                "revenue_year": float(snapshot.sell_price) * float(snapshot.recent_sales)
                * self.session.runner.config.simulation.days_per_year,
                "rival_price": (
                    None
                    if snapshot.rival_price is None
                    else float(snapshot.rival_price)
                ),
            },
            "settings": asdict(snapshot.settings),
            "choices": self._choices_dict(),
            **self._holding_dict(),
            "price_band": {"min": float(band.min), "max": float(band.max)},
            "messages": self.messages[::-1][:200],
            "history": list(self.history),
            "sale": self.sale,
            "review": self._review_dict(),
            "effects": list(self.effects[-12:])[::-1],
            "warnings": self._warnings(),
            "classification": self._classification_label(),
            "depot_value": self._depot_value(),
        }

    # ---- Cockpit 2: Ansichten, Makro-Verlauf, Wirkungsprotokoll, Warnungen ----

    VIEWS = {
        "compare": ("world_market", "compare"), "capacity": ("world_market", "capacity"),
        "market": ("world_market", "market"), "suppliers": ("world_market", "suppliers"),
        "population": ("world_market", "population"), "swiss_map": ("world_market", "swiss_map"),
        "macro": ("world_finance", "macro"), "banks": ("world_finance", "banks"),
        "stocks": ("world_finance", "stocks"), "commodities": ("world_finance", "commodities"),
        "trucks": ("world_finance", "trucks"), "research_tree": ("world_firm", "research_tree"),
        "autopilot": ("world_firm", "autopilot"), "classification": ("world_firm", "classification"),
        "glossary": ("world_firm", "glossary"),
    }

    def view(self, name: str, **query) -> dict:
        """Lese-Ansicht für einen Reiter (nur eigene und öffentliche Daten)."""
        import importlib
        with self._lock:
            if name not in self.VIEWS:
                return {"error": f"Unbekannte Ansicht: {name}"}
            if self.session is None or self.snapshot is None:
                return {"error": "Kein Spiel aktiv"}
            module_name, function_name = self.VIEWS[name]
            module = importlib.import_module(f"market_sim.game.{module_name}")
            extra: dict = {}
            if name in ("macro", "commodities"):
                extra["history"] = list(self.macro_history)
            elif name == "stocks":
                extra["depot"] = getattr(self.session, "depot", None)
            elif name == "banks" and query.get("amount"):
                try:
                    extra["amount"] = float(query["amount"])
                except (TypeError, ValueError):
                    return {"error": "Ungültiger Betrag"}
            try:
                data = getattr(module, function_name)(
                    self.session.runner, self.session.state, self.snapshot.firm_id, **extra)
                return _german_view(name, data)
            except Exception as exc:  # eine kaputte Ansicht darf das Spiel nicht stoppen
                return {"error": f"Ansicht {name} nicht verfügbar ({exc.__class__.__name__}: {exc})"}

    def _record_macro(self, snapshot) -> None:
        env = self.session.runner.env
        bank = getattr(env, "central_bank", None)
        long_run = getattr(self.session.runner, "long_run", None)
        row = {
            "label": f"J{snapshot.year} M{snapshot.month}",
            "policy_rate": float(getattr(bank, "policy_rate", 0.0) or 0.0),
            "inflation": float(getattr(bank, "inflation", getattr(long_run, "inflation", 0.0)) or 0.0),
            "fx_rate": float(getattr(env, "fx_rate", 1.0) or 1.0),
        }
        for name, value in (getattr(env, "commodity_price", {}) or {}).items():
            try:
                row[name] = float(value)
            except (TypeError, ValueError):
                pass
        try:
            row["strom"] = float(env.electricity_level())
        except Exception:
            pass
        self.macro_history.append(row)

    def _record_effect(self) -> None:
        if len(self.history) < 2:
            self._pending_changes = []
            return
        before, after = self.history[-2], self.history[-1]

        def delta(key):
            old, new = before.get(key, 0.0) or 0.0, after.get(key, 0.0) or 0.0
            return None if not old else round((new - old) / abs(old), 4)

        self.effects.append({
            "label": f"Jahr {after['year']}, Monat {after['month']}",
            "changes": list(self._pending_changes) or ["Keine Änderung"],
            "deltas": {"price": delta("sell_price"), "sales": delta("sales"),
                       "demand": delta("demand"), "cash": delta("cash")},
            "cash_change": after["cash"] - before["cash"],
        })
        self._pending_changes = []

    def _warnings(self) -> list[dict]:
        warnings: list[dict] = []
        snap = self.snapshot
        if snap is None or snap.game_over:
            return warnings
        months_left = None
        if len(self.history) >= 2:
            burn = self.history[-2]["cash"] - self.history[-1]["cash"]
            if burn > 0:
                months_left = snap.cash / burn
        if snap.cash < 0:
            warnings.append({"level": "rot", "text": "Die Kasse ist im Minus. Ohne Gegenmassnahme droht der Konkurs."})
        elif months_left is not None and months_left < 6:
            warnings.append({"level": "gelb", "text": f"Die Kasse reicht beim jetzigen Verlust noch etwa {months_left:.0f} Monate."})
        if snap.backlog > max(1.0, snap.recent_demand) * 3:
            warnings.append({"level": "gelb", "text": "Grosser Rückstand: Kunden warten. Mehr produzieren oder Überstunden prüfen."})
        if snap.inventory > max(1.0, snap.recent_demand) * 30:
            warnings.append({"level": "gelb", "text": "Sehr viel Lager: bindet Geld und kostet Lagerkosten."})
        if snap.rival_price and snap.sell_price > snap.rival_price * 1.25:
            warnings.append({"level": "gelb", "text": "Dein Preis liegt mehr als 25 % über der Konkurrenz."})
        try:
            from market_sim.game import holding_player
            for fid in holding_player.daughters(self.session.runner, snap.firm_id):
                if self.session.ceo_book.ceo_of(fid) is None:
                    warnings.append({"level": "gelb", "text": f"{self.session.runner.network.firm(fid).name} hat keinen CEO."})
        except Exception:
            pass
        return warnings

    def _classification_label(self) -> str | None:
        try:
            from market_sim.kpi import ARCHETYPE_DE
            firm = self.session.runner.network.firm(self.snapshot.firm_id)
            return ARCHETYPE_DE.get(firm.archetype, firm.archetype)
        except Exception:
            return None

    def _depot_value(self) -> float:
        depot = getattr(self.session, "depot", None)
        if depot is None:
            return 0.0
        try:
            return float(sum(p["value"] for p in depot.positions(self.session.runner)))
        except Exception:
            return 0.0

    def _holding_dict(self) -> dict:
        """Holding, kaufbare Firmen und CEOs (Phase 4)."""
        from market_sim.game import holding_player
        session, snap = self.session, self.snapshot
        runner, state = session.runner, session.state
        dpy = runner.config.simulation.days_per_year
        day = int(getattr(session, "_last_day", 0))
        try:
            targets = sorted(holding_player.buy_targets(runner, state, snap.firm_id),
                             key=lambda t: t["price"])[:30] if not snap.game_over else []
            holding = holding_player.holding_info(runner, state, snap.firm_id)
        except Exception:  # Holding-Logik aus oder Firma weg
            targets, holding = [], None
        return {
            "holding": holding,
            "targets": targets,
            "ceos": session.ceo_book.roster(snap.year, day, dpy),
            "ceo_of": dict(session.ceo_book.assignments),
            "order_results": list(session.order_results),
        }

    def _review_dict(self) -> dict | None:
        """Rückblick nach Spielende (einmal berechnet)."""
        if not self.snapshot.game_over or not getattr(self.session, "finished", False):
            return None
        cached = getattr(self, "_review_cache", None)
        if cached is not None and cached[0] is self.session:
            return cached[1]
        from market_sim.game.review import build_review
        try:
            review = build_review(self.session.runner, self.session.state, self.snapshot.firm_id,
                                  self.protocol, self.sale, self.snapshot.reason,
                                  getattr(self, "_start_price", None))
        except Exception as exc:  # Rückblick darf das Spielende nie verhindern
            review = {"summary": f"Der Rückblick konnte nicht berechnet werden ({exc.__class__.__name__})."}
        self._review_cache = (self.session, review)
        return review

    def _choices_dict(self) -> dict:
        """Aktuelle Entscheide der Spielerfirma (None = Autopilot)."""
        choice = self.session.runner.player_choices.get(self.snapshot.firm_id)
        return (choice or PlayerChoices()).to_dict()

    def _research_options(self) -> list[dict]:
        """Forschungsstufen, die die Spielerfirma jetzt wählen könnte."""
        if self.session is None or self.snapshot is None:
            return []
        lab = getattr(self.session.runner, "lab", None)
        options = getattr(lab, "options", None)
        if not callable(options):
            return []
        try:
            firm = self.session._current_firm()
            return [
                {
                    "name": stage.name,
                    "label": stage.name,
                    "cost": float(stage.cost),
                    "effect": float(stage.effect),
                }
                for stage in options(firm)
            ]
        except Exception:
            return []

    @staticmethod
    def _clean_name(name: str) -> str:
        """Entfernt Zeichen, die nicht in einen Spielstandnamen gehören."""
        return re.sub(r"[^A-Za-z0-9_\-äöüÄÖÜ ]", "", name).strip()
