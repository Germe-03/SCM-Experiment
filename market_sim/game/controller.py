from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import datetime
from pathlib import Path
import math
import re
import threading

from market_sim.game.choices import PlayerChoices
from market_sim.game.change_log import describe_changes
from market_sim.game.messages import messages_for
from market_sim.game.player import PlayerSettings
from market_sim.game.saves import SaveGame, list_saves, read_save, replay, write_save
from market_sim.game.session import BRANCHES, GameSession, RoundSnapshot
from market_sim.game.world_firm import year_baseline

YEARS_CHOICES = (5, 10, 20, 30, 40, 50)

ROHSTOFFE_DE = {
    "co2": "CO2", "cork": "Kork", "fruit": "Früchte", "grapes": "Trauben", "hops": "Hopfen",
    "malt": "Malz", "packaging": "Verpackung", "glass": "Glas", "sugar": "Zucker",
    "water": "Wasser", "wheat": "Weizen", "barley": "Gerste", "electricity": "Strom",
    "energy": "Energie", "aluminium": "Aluminium", "pet": "PET", "yeast": "Hefe",
    "grain": "Getreide", "potatoes": "Kartoffeln", "wood": "Holz", "labels": "Etiketten",
}
STUFEN_DE = {"factory": "Hersteller", "wholesaler": "Grosshändler", "distributor": "Verteiler",
             "retailer": "Detailhandel"}

REGIONEN_DE = {"genfersee": "Genferseeregion", "bern": "Bern", "jura_freiburg": "Jura/Freiburg",
               "nordwestschweiz": "Nordwestschweiz", "zuerich": "Zürich", "ostschweiz": "Ostschweiz",
               "zentralschweiz": "Zentralschweiz", "tessin": "Tessin"}
BRANCHEN_DE = {**STUFEN_DE, "truck_dealer": "Lastwagenhandel", "bank": "Bank", "courier": "Kurier"}

KATEGORIEN_DE = {
    "beer": "Bier", "wine": "Wein", "spirits": "Spirituosen",
    "softdrinks": "Softdrinks", "water": "Wasser",
}


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
    if name == "suppliers" and isinstance(data, dict):
        for row in data.get("candidates", []):
            row["region"] = REGIONEN_DE.get(row.get("region"), row.get("region"))
    if name == "stocks" and isinstance(data, dict):
        for row in data.get("listed", []):
            row["branch"] = BRANCHEN_DE.get(row.get("branch"), row.get("branch"))
    if name == "swiss_map" and isinstance(data, dict):
        for firm in data.get("firms", []):
            firm["stage"] = STUFEN_DE.get(firm.get("stage"), firm.get("stage"))
            if isinstance(firm.get("category"), str):
                firm["category"] = KATEGORIEN_DE.get(firm["category"], firm["category"])
    if name == "compare" and isinstance(data, dict):
        for row in data.get("rows", []):
            if isinstance(row, dict) and isinstance(row.get("category"), str):
                row["category"] = KATEGORIEN_DE.get(row["category"], row["category"])
    if name == "market" and isinstance(data, dict):
        for category in data.get("categories", []):
            if isinstance(category, dict) and isinstance(category.get("name"), str):
                category["name"] = KATEGORIEN_DE.get(category["name"], category["name"])
    if name == "reports" and isinstance(data, dict):
        for firm in data.get("firms", []):
            if isinstance(firm, dict):
                firm["stage"] = STUFEN_DE.get(firm.get("stage"), firm.get("stage"))
    if name == "takeover_offers" and isinstance(data, dict):
        for offer in data.get("offers", []):
            if isinstance(offer, dict):
                offer["stage"] = STUFEN_DE.get(offer.get("stage"), offer.get("stage"))
    # Allgemein: jede Ansicht mit einer Kategorienliste aus Dicts mit "name" übersetzen.
    if isinstance(data, dict):
        for category in data.get("categories", []) or []:
            if isinstance(category, dict) and isinstance(category.get("name"), str):
                category["name"] = KATEGORIEN_DE.get(category["name"], category["name"])
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
        self.game_years = self.years or 10
        self.days_per_year = days_per_year
        self.session: GameSession | None = None
        self.snapshot: RoundSnapshot | None = None
        self.protocol: SaveGame | None = None
        self.history: list[dict] = []
        self.price_history: list[dict] = []
        self.messages: list[dict] = []
        self.macro_history: list[dict] = []
        self.purchase_history: list[dict] = []
        self.stock_history: list[dict] = []
        self.effects: list[dict] = []
        self._pending_changes: list[str] = []
        self._year_totals: dict[int, tuple[float, float]] = {}
        self._seen_notices: set = set()
        self.sale: dict | None = None
        self._options_cache: dict | None = None

    def options(self) -> dict:
        """Gibt Branchen, Regionen und Kategorien zurück."""
        with self._lock:
            if self._options_cache is not None:
                regions = self._options_cache.get("regions", [])
                return {
                    **self._options_cache,
                    "research": self._research_options(),
                    "years_choices": list(YEARS_CHOICES),
                    "region_labels": {region: REGIONEN_DE.get(region, region) for region in regions},
                }

            regions = []
            categories = []
            banks = []
            offences = []
            try:
                session = GameSession(self.seed, self.game_years, self.days_per_year)
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
            return {
                **self._options_cache,
                "research": self._research_options(),
                "years_choices": list(YEARS_CHOICES),
                "region_labels": {region: REGIONEN_DE.get(region, region) for region in regions},
            }

    def new_game(
        self,
        branch: str,
        name: str,
        region: str | None = None,
        category: str | None = None,
        years: int | None = None,
    ) -> dict:
        """Gründet eine Firma und startet ein neues Spiel."""
        with self._lock:
            try:
                if years is not None and years not in YEARS_CHOICES:
                    raise ValueError("Ungültige Spieldauer")
                game_years = years if years is not None else (self.years if self.years is not None else 10)
                session = GameSession(
                    self.seed, self.years, self.days_per_year,
                    game_years=game_years,
                    dashboard_dir=self.save_dir.parent / "spiele",
                )
                game_years = session.game_years
                session.found(branch, name, region, category)
                snapshot = session.start()
                protocol = SaveGame(
                    seed=self.seed,
                    years=game_years,
                    days_per_year=self.days_per_year,
                    branch=branch,
                    name=name,
                    region=region,
                    category=category,
                    rounds=[],
                )

                self.game_years = game_years
                self.session = session
                self.snapshot = snapshot
                self.protocol = protocol
                self.history = []
                self.price_history = []
                self.messages = []
                self.macro_history = []
                self.purchase_history = []
                self.stock_history = []
                self.effects = []
                self._pending_changes = []
                self._year_totals = {}
                self._seen_notices = set()
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
                unit_size = self._unit_size()
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
                            if value is None or str(value).strip() == "":
                                updates[key] = None
                            else:
                                bottles = int(value)
                                updates[key] = (
                                    math.ceil(bottles / unit_size) if bottles > 0 else bottles
                                )
                        else:
                            updates[key] = str(value)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"Ungültige Einstellung: {key}") from exc

                new_settings = replace(current, **updates)
                choices_copy = dict(choices or {})
                orders_copy = dict(orders or {})
                if "expand" in orders_copy:
                    choices_copy["expand_order"] = self._bottles_to_units(
                        orders_copy["expand"], unit_size
                    )
                elif "expand_order" in choices_copy:
                    choices_copy["expand_order"] = self._bottles_to_units(
                        choices_copy["expand_order"], unit_size
                    )
                session_orders = dict(orders_copy)
                session_orders.pop("expand", None)
                self._apply_brand_suppliers(choices_copy)

                self._pending_changes = describe_changes(
                    current, updates, choices or {}, orders or {}
                )
                snapshot = self.session.end_round(
                    new_settings,
                    choices_copy or None,
                    session_orders or None,
                )
                if self.protocol is not None:
                    # Alte Spielstände ohne "choices": auf gleiche Länge auffüllen.
                    while len(self.protocol.choices) < len(self.protocol.rounds):
                        self.protocol.choices.append({})
                    self.protocol.rounds.append(asdict(new_settings))
                    self.protocol.choices.append(dict(choices_copy))
                    while len(self.protocol.orders) < len(self.protocol.rounds) - 1:
                        self.protocol.orders.append({})
                    self.protocol.orders.append(dict(session_orders))
                self.snapshot = snapshot
                self._process(snapshot)
                return self._state()
            except (ValueError, RuntimeError, KeyError, OSError) as exc:
                return {"error": str(exc)}

    def skip_year(self, settings: dict | None = None, choices: dict | None = None,
                  orders: dict | None = None) -> dict:
        """Erste Runde mit den Eingaben, dann ohne Halt bis zum ersten Halt im nächsten Jahr."""
        with self._lock:
            if self.session is None or self.snapshot is None:
                return {"error": "Kein Spiel aktiv"}
            start_year = int(self.snapshot.year)
            result = self.end_round(settings, choices, orders)
            guard = 0
            while (
                "error" not in result
                and self.snapshot is not None
                and not self.snapshot.game_over
                and int(self.snapshot.year) == start_year
                and guard < 100
            ):
                guard += 1
                result = self.end_round()
            return result

    def reset(self) -> dict:
        """Beendet das Spiel ohne Speichern und kehrt zur Gründung zurück."""
        with self._lock:
            self.session = None
            self.snapshot = None
            self.protocol = None
            self.history = []
            self.price_history = []
            self.messages = []
            self.macro_history = []
            self.purchase_history = []
            self.stock_history = []
            self.effects = []
            self._pending_changes = []
            self._year_totals = {}
            self._seen_notices = set()
            self.sale = None
            return {"running": False}

    def dashboard_file(self):
        """Pfad des fertigen Dashboards des aktuellen Spiels oder None."""
        with self._lock:
            session = self.session
            path = getattr(session, "dashboard_path", None) if session is not None else None
            if path is not None and getattr(session, "dashboard_status", None) == "fertig":
                return Path(path)
            return None

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
                self.game_years = save.years or self.years or 10
                self.history = []
                self.price_history = []
                self.messages = []
                self.macro_history = []
                self.purchase_history = []
                self.stock_history = []
                self.effects = []
                self._pending_changes = []
                self._year_totals = {}
                self._seen_notices = set()
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

    def check(
        self,
        settings: dict | None = None,
        choices: dict | None = None,
        orders: dict | None = None,
    ) -> dict:
        """Prüft Einstellungen und Entscheide für die nächste Runde."""
        with self._lock:
            if self.session is None or self.snapshot is None:
                return {"error": "Kein Spiel aktiv"}
            try:
                from market_sim.game import views2

                warnings = views2.check_plan(
                    self.session.runner,
                    self.session.state,
                    self.snapshot.firm_id,
                    settings or {},
                    choices or {},
                    orders or {},
                    self._unit_size(),
                    self.snapshot,
                )
                return {"warnings": warnings}
            except Exception:
                return {"warnings": []}

    def _unit_size(self) -> int:
        """Anzahl Flaschen pro Simulationseinheit (mindestens 1)."""
        try:
            size = int(self.session.runner.config.unit_scale.real_units_per_sim_unit)
        except Exception:
            size = 1
        return max(1, size)

    @staticmethod
    def _bottles_to_units(value, unit_size: int):
        """Wandelt eine Flaschenmenge in Simulationseinheiten um."""
        if value is None or str(value).strip() == "":
            return None
        if isinstance(value, dict):
            converted = dict(value)
            for key in ("quantity", "amount", "bottles", "capacity"):
                if key in converted:
                    bottles = float(converted[key])
                    converted[key] = math.ceil(bottles / unit_size) if bottles > 0 else bottles
                    return converted
            return converted
        bottles = float(value)
        return math.ceil(bottles / unit_size) if bottles > 0 else bottles

    def _process(self, snapshot: RoundSnapshot) -> None:
        """Übernimmt Verlauf und Meldungen eines Snapshots."""
        unit_size = self._unit_size()  # ohne laufende Session gilt Groesse 1
        if self.session is not None:
            # Stand zu Jahresbeginn merken: der erste Halt eines Jahres legt ihn an.
            try:
                year_baseline(self.session.runner, snapshot.firm_id, int(snapshot.year))
            except Exception:
                pass
        if not self.history:
            self._start_price = float(snapshot.settings.base_price)
        self.history.append(
            {
                "year": int(snapshot.year),
                "month": int(snapshot.month),
                "cash": float(snapshot.cash),
                "profit": float(snapshot.profit),
                "sell_price": round(float(snapshot.sell_price), 2),
                "sales": float(snapshot.recent_sales) * unit_size,
                "demand": float(snapshot.recent_demand) * unit_size,
                "inventory": int(snapshot.inventory) * unit_size,
                "backlog": int(snapshot.backlog) * unit_size,
            }
        )
        if self.session is None:
            return

        try:
            runtime = self.session.runner.env.runtimes.get(snapshot.firm_id)
            base = year_baseline(
                self.session.runner, snapshot.firm_id, int(snapshot.year)
            )
            if runtime is not None:
                revenue_year = float(runtime.revenue) - base["revenue"]
                profit_year = float(runtime.profit) - base["profit"]
                self._year_totals[int(snapshot.year)] = (revenue_year, profit_year)
        except Exception:
            pass

        try:
            from market_sim.game import views2

            calculation = views2.calculation(
                self.session.runner,
                self.session.state,
                snapshot.firm_id,
            )
            purchase_price = calculation.get("purchase_price") if isinstance(calculation, dict) else None
            purchase_price = None if purchase_price is None else round(float(purchase_price), 2)
        except Exception:
            purchase_price = None
        try:
            sell_price = round(float(snapshot.sell_price), 2)
        except Exception:
            sell_price = None
        self.price_history.append({
            "label": f"Jahr {snapshot.year}, Monat {snapshot.month}",
            "purchase": purchase_price,
            "sell": sell_price,
        })

        self._record_macro(snapshot)
        self._record_effect()
        self._record_stock(snapshot)
        try:
            prices = self.session.runner.env.component_prices(snapshot.firm_id)
            if prices:
                self.purchase_history.append({
                    "label": f"J{snapshot.year} M{snapshot.month}",
                    **{str(k): round(float(v), 4) for k, v in prices.items()},
                })
        except Exception:
            pass
        try:
            names = {
                firm.id: firm.name
                for firm in self.session.runner._firms()
            }
        except Exception:
            names = {}
        try:
            for message in messages_for(snapshot.events, snapshot.firm_id, names):
                # Gleiche Meldung höchstens einmal pro Jahr (z.B. «Kapazitätsgrenze erreicht»).
                key = ("text", message.get("year"), message.get("text"))
                if key in self._seen_notices:
                    continue
                self._seen_notices.add(key)
                self.messages.append(message)
        except Exception:
            pass

        try:
            years_left = (
                None
                if snapshot.game_over
                else max(0, self.game_years - snapshot.year + 1)
            )
            from market_sim.game.notices import build_notices

            self.messages.extend(build_notices(
                self.session.runner,
                self.session.state,
                snapshot.firm_id,
                snapshot.year,
                int(getattr(self.session, "_last_day", 0)),
                self._seen_notices,
                self.session.ceo_book,
                years_left,
                snapshot.events,
            ))
        except Exception:
            pass

    def _last_year_totals(self, year: int, firm_id) -> tuple[float, float]:
        """Liest den veröffentlichten Umsatz und Nettogewinn des Vorjahres."""
        try:
            annual_reports = getattr(self.session.runner, "annual_reports", {})
            reports = annual_reports.get(year, annual_reports.get(str(year), {}))
            report = reports.get(firm_id) if isinstance(reports, dict) else None
            if report is not None:
                if not isinstance(report, dict):
                    report = vars(report)
                income = report.get("income_statement")
                income = income if isinstance(income, dict) else {}
                revenue = report.get("revenue", income.get("revenue"))
                net_income = report.get("net_income", income.get("net_income"))
                if revenue is not None or net_income is not None:
                    return (
                        round(float(revenue or 0.0), 2),
                        round(float(net_income or 0.0), 2),
                    )
        except Exception:
            pass
        try:
            revenue, profit = self._year_totals.get(year, (0.0, 0.0))
            return round(float(revenue), 2), round(float(profit), 2)
        except Exception:
            return 0.0, 0.0

    def _state(self) -> dict:
        """Baut das JSON für den aktuellen Spielzustand."""
        if self.session is None or self.snapshot is None or self.protocol is None:
            return {"running": False}

        snapshot = self.snapshot
        stage = BRANCHES[self.protocol.branch][0]
        band = self.session.runner.config.stage_prices[stage]
        runner = self.session.runner
        unit_size = self._unit_size()

        # Umsatz und Gewinn des laufenden Jahres: Laufzeitwerte minus Stand zu Jahresbeginn.
        revenue_year = 0.0
        profit_year = 0.0
        try:
            runtime = runner.env.runtimes.get(snapshot.firm_id)
            base = year_baseline(runner, snapshot.firm_id, int(snapshot.year))
            if runtime is not None:
                revenue_year = float(runtime.revenue) - base["revenue"]
                profit_year = float(runtime.profit) - base["profit"]
        except Exception:
            revenue_year = 0.0
            profit_year = 0.0
        try:  # gleiche Rechnung wie im Reiter Abschlüsse (Lageraufbau ist kein Aufwand)
            from market_sim import financials
            statement = financials.income_statement(runner, snapshot.firm_id, None)
            if statement and statement.get("revenue"):
                revenue_year = float(statement["revenue"])
                profit_year = float(statement["net_income"])
        except Exception:
            pass

        try:
            capacity_per_day = float(runner.env._effective_capacity(snapshot.firm_id)) * unit_size
        except Exception:
            capacity_per_day = 0.0

        try:
            revenue_last_year, profit_last_year = self._last_year_totals(
                int(snapshot.year) - 1, snapshot.firm_id
            )
        except Exception:
            revenue_last_year, profit_last_year = 0.0, 0.0

        month_names = (
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        )
        month = int(snapshot.month)
        month_name = month_names[month - 1] if 1 <= month <= 12 else f"Monat {month}"
        years_total = self.game_years
        years_left = max(0, years_total - int(snapshot.year) + 1)
        if not snapshot.game_over:
            end_reason_text = None
        elif snapshot.reason == "konkurs":
            end_reason_text = "Deine Firma ist in Konkurs gegangen: Das Geld reichte nicht mehr für Rechnungen und Löhne."
        elif snapshot.reason == "verkauft":
            end_reason_text = "Du hast deine Firma verkauft. Das Spiel ist zu Ende."
        else:
            end_reason_text = f"Die {years_total} Jahre sind um. Das Spiel ist zu Ende."

        settings_data = asdict(snapshot.settings)
        if settings_data.get("order_qty") is not None:
            try:
                settings_data["order_qty"] = int(settings_data["order_qty"]) * unit_size
            except Exception:
                pass

        return {
            "running": True,
            "game_over": bool(snapshot.game_over),
            "reason": snapshot.reason,
            "end_reason_text": end_reason_text,
            "year": int(snapshot.year),
            "month": month,
            "month_name": month_name,
            "years_total": years_total,
            "years_left": years_left,
            "unit_size": unit_size,
            "firm": {
                "id": snapshot.firm_id,
                "name": snapshot.name,
                "branch": self.protocol.branch,
            },
            "kpis": {
                "cash": round(float(snapshot.cash), 2),
                "inventory": int(snapshot.inventory) * unit_size,
                "backlog": int(snapshot.backlog) * unit_size,
                "employees": int(snapshot.employees),
                "sell_price": round(float(snapshot.sell_price), 2),
                "profit": float(snapshot.profit),
                "recent_demand": float(snapshot.recent_demand) * unit_size,
                "recent_sales": float(snapshot.recent_sales) * unit_size,
                "revenue_year": revenue_year,
                "profit_year": profit_year,
                "revenue_last_year": revenue_last_year,
                "profit_last_year": profit_last_year,
                "capacity_per_day": capacity_per_day,
                "rival_price": (
                    None
                    if snapshot.rival_price is None
                    else round(float(snapshot.rival_price), 2)
                ),
            },
            "settings": settings_data,
            "choices": self._choices_dict(),
            **self._holding_dict(),
            "price_band": {"min": round(float(band.min), 2), "max": round(float(band.max), 2)},
            "messages": self.messages[::-1][:200],
            "history": list(self.history),
            "sale": self.sale,
            "review": self._review_dict(),
            "effects": list(self.effects[-12:])[::-1],
            "warnings": self._warnings(),
            "classification": self._classification_label(),
            "depot_value": self._depot_value(),
            "dashboard_status": getattr(self.session, "dashboard_status", None),
            "dashboard_progress": int(getattr(self.session, "dashboard_progress", 0) or 0),
            "dashboard_url": "/dashboard" if getattr(self.session, "dashboard_status", None) else None,
            "sim_years": int(runner.config.simulation.years),
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
        "costs": ("world_firm", "costs"), "bottleneck": ("world_firm", "bottleneck"),
        "glossary": ("world_firm", "glossary"),
        "financials": ("views2", "financials"), "reports": ("views2", "reports"),
        "calculation": ("views2", "calculation"), "pricing": ("views2", "pricing"),
        "takeover_offers": ("views2", "takeover_offers"), "assortment": ("views2", "assortment"),
        "purchasing": ("views3", "purchasing"), "deliveries": ("views3", "deliveries"),
        "daughters": ("views3", "daughters"), "stocks_all": ("views3", "stocks_all"),
        "inventory": ("views4", "inventory"), "brand_sources": ("views4", "brand_sources"),
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
            elif name in ("financials", "calculation", "pricing"):
                extra["year"] = int(self.snapshot.year)
            elif name == "purchasing":
                extra["history"] = list(self.purchase_history)
            elif name == "inventory":
                extra["stock_history"] = list(self.stock_history)
            elif name == "costs":
                extra["year"] = int(self.snapshot.year)
            elif name == "stocks":
                extra["depot"] = getattr(self.session, "depot", None)
            elif name == "pricing":
                extra["price_history"] = list(self.price_history)
            elif name == "banks" and query.get("amount"):
                try:
                    extra["amount"] = float(query["amount"])
                except (TypeError, ValueError):
                    return {"error": "Ungültiger Betrag"}
            try:
                data = getattr(module, function_name)(
                    self.session.runner, self.session.state, self.snapshot.firm_id, **extra)
                if name == "capacity" and isinstance(data, dict):
                    unit = int(self.session.runner.config.unit_scale.real_units_per_sim_unit)
                    for key in ("capacity_per_day", "inventory", "backlog"):
                        if isinstance(data.get(key), (int, float)):
                            data[key] = data[key] * unit
                    for key in ("demand", "sales", "stage_demand"):
                        if isinstance(data.get(key), dict):
                            data[key] = {k: (v * unit if isinstance(v, (int, float)) else v)
                                         for k, v in data[key].items()}
                return _german_view(name, data)
            except Exception as exc:  # eine kaputte Ansicht darf das Spiel nicht stoppen
                return {"error": f"Ansicht {name} nicht verfügbar ({exc.__class__.__name__}: {exc})"}

    def _apply_brand_suppliers(self, choices_copy: dict) -> None:
        """brand_suppliers (Marke -> Grosshändler) in supplier_shares (Lieferant -> Flaschen) umrechnen."""
        try:
            runner = self.session.runner
            current = runner.player_choices.get(self.snapshot.firm_id)
            suppliers = choices_copy.get("brand_suppliers", getattr(current, "brand_suppliers", None))
            if not isinstance(suppliers, dict) or not suppliers:
                # Feste Lieferanten wieder entfernt: auch die daraus berechneten Anteile entfernen.
                if "brand_suppliers" in choices_copy and getattr(current, "supplier_shares", None):
                    choices_copy["supplier_shares"] = None
                return
            plan = choices_copy.get("brand_plan", getattr(current, "brand_plan", None))
            plan = plan if isinstance(plan, dict) else {}
            shares: dict = {}
            for brand_id, supplier_id in suppliers.items():
                if not supplier_id:
                    continue
                try:
                    amount = float(plan.get(brand_id, 0) or 0)
                except (TypeError, ValueError):
                    amount = 0.0
                shares[supplier_id] = shares.get(supplier_id, 0.0) + max(0.0, amount)
            if shares and sum(shares.values()) <= 0:
                shares = {supplier_id: 1.0 for supplier_id in shares}
            if shares:
                choices_copy["supplier_shares"] = shares
        except Exception:
            pass

    def _record_stock(self, snapshot) -> None:
        """Lagerstand je Marke (Flaschen) dieser Runde merken (für Lager-Verlauf und Absatz pro Tag)."""
        try:
            runner = self.session.runner
            runtime = runner.env.runtimes.get(snapshot.firm_id)
            unit = self._unit_size()
            stock = getattr(runtime, "stock", None) or {}
            month = int(snapshot.month)
            names = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                     "September", "Oktober", "November", "Dezember")
            month_name = names[month - 1] if 1 <= month <= 12 else f"Monat {month}"
            self.stock_history.append({
                "label": f"Jahr {int(snapshot.year)}, {month_name}",
                "year": int(snapshot.year),
                "month": month,
                "brands": {str(b): float(v) * unit for b, v in stock.items()},
            })
        except Exception:
            pass

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
            targets = [
                {**target, "price": round(float(target["price"]), 2)}
                if isinstance(target, dict) and target.get("price") is not None else target
                for target in targets
            ]
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
        result = (choice or PlayerChoices()).to_dict()
        if result.get("expand_order") is not None:
            try:
                result["expand_order"] = result["expand_order"] * self._unit_size()
            except Exception:
                pass
        return result

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
