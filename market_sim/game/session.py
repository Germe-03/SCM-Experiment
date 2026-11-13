"""Schnittstelle für den rundenbasierten Spielmodus."""

from __future__ import annotations

import math

from dataclasses import dataclass, replace
import queue
import threading
from typing import TYPE_CHECKING

from market_sim.game.ceos import CAUTIOUS_TENDENCY, STYLE_TENDENCY, CeoBook
from market_sim.game.choices import PlayerChoices
from market_sim.game import holding_player
from market_sim.game.player import PlayerPolicy, PlayerSettings
from market_sim.models import STAGES
from market_sim.policies import FirmPolicy, policy_for_firm
from market_sim.run import build_runner

if TYPE_CHECKING:
    from market_sim.runner import RunResult, RunState, SimulationRunner


BRANCHES = {
    "hersteller": ("factory", None),
    "grosshaendler": ("wholesaler", None),
    "verteiler": ("distributor", None),
    "detailhaendler": ("retailer", "store"),
    "gastro": ("retailer", "restaurant"),
}


@dataclass
class RoundSnapshot:
    year: int
    month: int
    firm_id: str
    name: str
    cash: float
    inventory: int
    backlog: int
    employees: int
    sell_price: float
    profit: float
    recent_demand: float
    recent_sales: float
    rival_price: float | None
    events: list[dict]
    settings: PlayerSettings
    game_over: bool = False
    reason: str | None = None


@dataclass
class SaleResult:
    year: int
    month: int
    price: float
    firm_id: str


class GameSession:
    """Steuert eine Simulation mit monatlichen Haltepunkten."""

    def __init__(
        self,
        seed: int = 0,
        years: int | None = None,
        days_per_year: int | None = None,
        config=None,
        game_years: int | None = None,
        dashboard_dir=None,
    ) -> None:
        # years = Gesamtlänge der Simulation (None = config.simulation.years, 50);
        # game_years = Spielzeit, danach läuft die Firma im Autopilot weiter.
        self.runner, _ = build_runner(years, seed, days_per_year, config)
        total = int(self.runner.config.simulation.years)
        self.game_years = min(total, int(game_years)) if game_years else total
        self.seed = seed
        self.dashboard_dir = dashboard_dir
        self.dashboard_status: str | None = None
        self.dashboard_progress: int = 0
        self.dashboard_path = None
        self._done = threading.Event()
        self.result: RunResult | None = None
        self.finished = False
        self.force_end = False  # True: Spiel endet am nächsten Halt (bis zum Ende simulieren)
        self._founding: tuple[str, str, str | None, str | None] | None = None
        self._firm_id: str | None = None
        self._firm = None
        self._state: RunState | None = None
        self.state: RunState | None = None
        self._started = False
        self._holding = False
        self._reason: str | None = None
        self._event_mark = 0
        self._settings = None
        self._last_year = 1
        self._last_day = 0
        self.ceo_book = CeoBook()
        self.depot = None  # Aktien-Depot (Cockpit 2), angelegt beim ersten Kauf
        self.order_results: list[dict] = []
        self.extra_events: list[dict] = []
        self._pending_orders: dict = {}
        self._last_halt_day: int | None = None
        self._to_main: queue.Queue = queue.Queue()
        self._to_thread: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def found(
        self,
        branch: str,
        name: str,
        region: str | None = None,
        category: str | None = None,
    ) -> str:
        """Merkt die Firmengründung für den Start vor."""

        if self._started:
            raise RuntimeError("Die Firma muss vor dem Start gegründet werden")
        if branch not in BRANCHES:
            raise ValueError(f"Unbekannte Branche: {branch}")

        stage, _ = BRANCHES[branch]
        geography = getattr(self.runner.config, "geography", None)
        if region is not None and (
            geography is None
            or not getattr(geography, "enabled", False)
            or region not in [item.name for item in geography.regions]
        ):
            raise ValueError(f"Unbekannte Region: {region}")

        if category is not None:
            categories = getattr(self.runner.config, "categories", None)
            names = [item.name for item in categories.categories] if categories is not None else []
            if category not in names:
                raise ValueError(f"Unbekannte Kategorie: {category}")

        self._founding = (branch, name, region, category)
        return f"{stage}_p01"

    def start(self) -> RoundSnapshot:
        """Gründet die Spielerfirma und startet die Simulation."""

        if self._started:
            raise RuntimeError("Die Sitzung wurde bereits gestartet")
        if self._founding is None:
            raise RuntimeError("Vor dem Start muss eine Firma gegründet werden")

        branch, name, region, category = self._founding
        stage, _ = BRANCHES[branch]
        runner = self.runner
        cfg = runner.config.market_entry
        state = runner.start()
        pool = [
            firm for firm in runner.network.firms_in(stage)
            if runner.env.runtimes[firm.id].active
        ]

        if stage == "retailer":
            channel = BRANCHES[branch][1]
            pool = [firm for firm in pool if firm.channel == channel]
        if category is not None:
            same = [
                firm for firm in pool
                if firm.category == category and not (stage == "factory" and firm.importer)
            ]
            pool = same or pool

        if not pool:
            raise ValueError(f"Keine aktive Vorlage für die Branche {branch}")

        template = sorted(
            pool,
            key=lambda firm: (runner.env.runtimes[firm.id].cash, firm.id),
        )[len(pool) // 2]
        firm_id = f"{stage}_p01"
        updates = {
            "id": firm_id,
            "name": name,
            "cash": cfg.start_cash_fraction * runner._entry_cash[stage],
            "capacity": max(1, round(template.capacity * cfg.start_capacity_fraction)),
            "machine_capacity": (
                max(1, round(template.machine_capacity * cfg.start_capacity_fraction))
                if template.machine_capacity else 0
            ),
            # So viele Leute, wie die Startkapazität braucht: Mehr Personal würde nur Fixkosten für
            # Kapazität erzeugen, die eine neue Firma noch gar nicht verkaufen kann.
            "employees": max(1, min(
                round(template.employees * cfg.start_capacity_fraction),
                round(max(1, round(template.capacity * cfg.start_capacity_fraction))
                      / max(0.1, float(template.productivity_per_employee))),
            )),
            "reputation": (cfg.start_reputation[0] + cfg.start_reputation[1]) / 2,
            "quality_level": template.quality_level * cfg.start_quality_fraction,
            "inventory": 0,
            "backlog": 0,
            "suppliers": [],
            "region": region or template.region,
            "extra_regions": [],
            "transport_mode": "service" if runner.config.trucks.enabled else "own",
        }
        if category is not None and template.category != category:
            updates.update(category=category)
        if stage == "factory" and category is not None:
            updates.update(importer=False)
        firm = template.model_copy(deep=True, update=updates)
        # Startpersonal passend zur Startkapazität (aufgerundet): Die Fixkosten richten sich nach
        # max(Kapazität, Personal × Produktivität). Zu viel Personal hiesse Fixkosten für Leerkapazität.
        import math
        productivity = max(0.1, float(firm.productivity_per_employee))
        firm.employees = max(1, min(firm.employees, math.ceil(firm.capacity / productivity)))

        settings = PlayerSettings.from_strategy(
            FirmPolicy().decide_annual(firm, None, runner.config)
        )
        settings.hiring_plan = 0  # eingestellt wird nur, wenn der Spieler es will
        runner.add_firm(firm, state, policy=PlayerPolicy(settings), announce=False)
        # Nach dem Eintritt (Produktivität ist jetzt die der Stufe): Personal auf die Startkapazität kürzen.
        added = runner.network.firm(firm.id)
        productivity = max(0.1, float(added.productivity_per_employee))
        added.employees = max(1, min(added.employees, math.ceil(added.capacity / productivity)))
        runner.env.runtimes[added.id].employees = added.employees
        runner._entry_year[firm.id] = 0
        if not hasattr(runner, "player_choices"):
            runner.player_choices = {}
            runner.env.player_choices = runner.player_choices
        runner.player_choices[firm.id] = PlayerChoices()
        runner.policies[firm.id].choices = runner.player_choices[firm.id]
        runner.policies[firm.id].env = runner.env
        if (
            stage == "factory"
            and firm.category == "wine"
            and not firm.importer
            and runner.env.brand_book is not None
        ):
            days = runner.config.simulation.days_per_year
            extra = (
                cfg.maturation_start_cash_factor * 1.0 * days
                * runner.env._effective_capacity(firm.id)
                * runner.env.unit_production_cost(firm)
            )
            runner.env.runtimes[firm.id].adjust_cash(extra, "Startkapital Reifezeit")

        self._started = True
        self._firm_id = firm.id
        self._firm = firm
        self._state = state
        self.state = state
        self._event_mark = len(state.events)
        runner.day_hook = self._hook
        self._thread = threading.Thread(
            target=self._run,
            args=(state,),
            daemon=True,
        )
        self._thread.start()
        return self._wait()

    def end_round(
        self,
        settings: PlayerSettings | None = None,
        choices: dict | None = None,
        orders: dict | None = None,
    ) -> RoundSnapshot:
        """Übernimmt optionale Einstellungen und Entscheide und wartet bis zum nächsten Halt."""

        if not self._started or self.finished or not self._holding:
            raise RuntimeError("Die Sitzung ist nicht an einem aktiven Halt")
        if choices:
            current = self.runner.player_choices.get(self._firm_id)
            if current is not None:
                current.update(choices)
        if settings is not None:
            policy = self.runner.policies.get(self._firm_id)
            old = policy.settings if isinstance(policy, PlayerPolicy) else None
            if old is not None and settings.wage_level != old.wage_level:
                # Mitarbeiter reagieren sofort auf den neuen Lohn.
                self._current_firm().wage_level = settings.wage_level
        self._pending_orders = orders if isinstance(orders, dict) else {}
        self.order_results = []
        self._holding = False
        self._to_thread.put(("continue", settings))
        return self._wait()

    def sell_firm(self) -> SaleResult:
        """Verkauft die Spielerfirma und lässt die Simulation zu Ende laufen."""

        if not self._started or self.finished or not self._holding:
            raise RuntimeError("Die Firma kann nur während eines Halts verkauft werden")

        runner = self.runner
        state = self._state
        firm_id = self._firm_id
        year, day = self._last_year, self._last_day
        runtime = runner.env.runtimes[firm_id]
        firm = self._current_firm()
        holdings = getattr(runner, "holdings", None)
        price = (
            holdings.market_value(runner, state, firm_id)
            if holdings is not None
            else max(0.0, runtime.cash)
        )
        month = day // runner.config.workforce.days_per_month + 1

        runner.policies[firm_id] = policy_for_firm(firm)
        runner.day_hook = None
        runner.player_choices.pop(firm_id, None)
        state.events.append({
            "year": year,
            "day": day,
            "firm": firm_id,
            "event": "player_sale",
            "details": f"Verkauf für {price:,.0f}",
        })
        self._reason = "verkauft"
        self._mark_dashboard_running()
        self._holding = False
        self.finished = True
        self._to_thread.put(("continue", None))
        return SaleResult(year=year, month=month, price=price, firm_id=firm_id)

    def _end_in_thread(self, reason: str, year: int, day: int) -> None:
        """Spielende im Simulationsthread: Firma an den Autopiloten, Simulation läuft weiter."""

        runner = self.runner
        firm_id = self._firm_id
        if reason == "ende":
            self._last_year = max(1, year - 1)
            self._last_day = max(0, runner.config.simulation.days_per_year - 1)
            try:
                runner.policies[firm_id] = policy_for_firm(self._current_firm())
            except Exception:
                pass
            runner.player_choices.pop(firm_id, None)
        runner.day_hook = None
        self._reason = reason
        self._mark_dashboard_running()
        self.finished = True
        self._holding = False
        self._to_main.put(self._snapshot(
            runner, self._state, self._last_year, self._last_day,
            game_over=True, reason=reason,
        ))

    def _mark_dashboard_running(self) -> None:
        if self.dashboard_status is None:
            self.dashboard_status = "laeuft"

    def wait_done(self, timeout: float | None = None) -> bool:
        """Wartet, bis Simulation und Dashboard fertig sind (für Tests)."""
        return self._done.wait(timeout)

    def _on_year_end(self, runner, state) -> None:
        self.dashboard_progress = int(state.year)

    def _run(self, state: RunState) -> None:
        """Führt die Simulation im Hintergrund aus, danach das Dashboard."""

        try:
            result = self.runner.continue_run(
                state,
                self.runner.config.simulation.years,
                on_year_end=self._on_year_end,
            )
        except Exception as exc:
            self.dashboard_status = "fehler" if self.finished else None
            self._to_main.put(("error", exc))
            self._done.set()
            return
        self.result = result
        self._to_main.put(("done", result))
        self._mark_dashboard_running()
        try:
            self.dashboard_path = self._write_dashboard(result)
            self.dashboard_status = "fertig"
        except Exception:
            self.dashboard_status = "fehler"
        self._done.set()

    def _write_dashboard(self, result):
        """Schreibt das Beobachter-Dashboard der ganzen Simulation."""
        from datetime import datetime
        from pathlib import Path
        import re
        from market_sim.dashboard import write_dashboard_html
        from market_sim.dashboard_data import build_dashboard_data

        runner = self.runner
        data = build_dashboard_data(result, runner.network, runner.config, self.seed)
        try:
            firm_name = runner.network.firm(self._firm_id).name
        except Exception:
            firm_name = self._firm_id or "spiel"
        slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", firm_name).strip("_") or "firma"
        base = Path(self.dashboard_dir) if self.dashboard_dir else Path("runs") / "spiele"
        target = base / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug}" / "dashboard.html"
        return write_dashboard_html(data, target).resolve()

    def _hook(
        self,
        runner: SimulationRunner,
        state: RunState,
        year: int,
        day: int,
    ) -> None:
        """Hält die Simulation am Monatsanfang an."""

        if day % runner.config.workforce.days_per_month != 0:
            return
        firm_id = self._firm_id
        self._state = state
        self.state = state
        if not runner.env.runtimes[firm_id].active:
            self._end_in_thread("konkurs", year, day)
            return
        if year > self.game_years or self.force_end:
            self._end_in_thread("ende", year, day)
            return

        self._last_year = year
        self._last_day = day
        self._holding_upkeep(year, day)
        if day == 0 and year > 1 and self.depot is not None:
            try:
                self.depot.pay_dividends(runner, state, firm_id)
            except Exception:  # Dividenden dürfen das Spiel nie stoppen
                pass
        self._to_main.put(self._snapshot(runner, state, year, day))
        _, settings = self._to_thread.get()
        self._apply_orders(self._pending_orders, year, day)
        self._pending_orders = {}
        self._holding_upkeep(year, day, upkeep=False)
        if settings is not None:
            runner.policies[firm_id].settings = settings

    def _apply_orders(self, orders: dict, year: int, day: int) -> None:
        """Führt die Aufträge im Simulationsthread aus."""

        if not isinstance(orders, dict):
            return

        runner = self.runner
        state = self._state
        player_id = self._firm_id
        self._apply_trade_orders(orders, year, day)
        dpy = runner.config.simulation.days_per_year
        daughters = set(holding_player.daughters(runner, player_id))

        if orders.get("buy"):
            result = holding_player.buy(
                runner, state, player_id, orders["buy"], year, day
            )
            self.order_results.append({
                "ok": bool(result.get("ok")),
                "message": result.get("message", "Der Kauf konnte nicht abgeschlossen werden"),
            })

        if orders.get("sell"):
            firm_id = orders["sell"]
            result = holding_player.sell_daughter(
                runner, state, player_id, firm_id, year, day
            )
            self.ceo_book.fire(firm_id)
            runner.player_choices.pop(firm_id, None)
            self.order_results.append({
                "ok": bool(result.get("ok")),
                "message": result.get("message", "Der Verkauf konnte nicht abgeschlossen werden"),
            })

        hires = orders.get("hire", {})
        if isinstance(hires, dict):
            for firm_id, nr in hires.items():
                if firm_id not in daughters:
                    self.order_results.append({
                        "ok": False,
                        "message": "Diese Firma ist keine Tochter der Holding",
                    })
                    continue
                try:
                    self.ceo_book.hire(firm_id, int(nr), year, day, dpy)
                except (TypeError, ValueError) as exc:
                    self.order_results.append({"ok": False, "message": str(exc)})
                else:
                    avatar = self.ceo_book.ceo_of(firm_id)
                    self.order_results.append({
                        "ok": True,
                        "message": f"{avatar.name} wurde als CEO eingestellt",
                    })

        fires = orders.get("fire", [])
        if isinstance(fires, list):
            for firm_id in fires:
                avatar = self.ceo_book.fire(firm_id)
                if avatar is None:
                    self.order_results.append({
                        "ok": False,
                        "message": "Diese Firma hat keinen CEO",
                    })
                else:
                    self.order_results.append({
                        "ok": True,
                        "message": f"{avatar.name} wurde entlassen",
                    })

        guidelines = orders.get("guidelines", {})
        if isinstance(guidelines, dict):
            for firm_id, values in guidelines.items():
                if not isinstance(values, dict):
                    continue
                choices = runner.player_choices.setdefault(firm_id, PlayerChoices())
                for key in ("payout_ratio", "auto_invest"):
                    if key in values:
                        setattr(choices, key, values[key])
                self.order_results.append({
                    "ok": True,
                    "message": "Leitplanken wurden gespeichert",
                })

    def _apply_trade_orders(self, orders: dict, year: int, day: int) -> None:
        """Cockpit 2: Kredit, Lastwagen und Aktien (market_sim/game/actions.py)."""
        from market_sim.game import actions
        runner, state, fid = self.runner, self._state, self._firm_id

        def run(call):
            try:
                result = call()
            except Exception as exc:  # ein Auftrag darf das Spiel nie stoppen
                result = {"ok": False, "message": f"Auftrag fehlgeschlagen ({exc.__class__.__name__})"}
            self.order_results.append({"ok": bool(result.get("ok")), "message": str(result.get("message", ""))})

        loan = orders.get("loan")
        if isinstance(loan, dict) and loan.get("amount"):
            run(lambda: actions.take_loan(runner, state, fid, float(loan["amount"]), loan.get("bank_id"), year, day))
        self._apply_contract_orders(orders, run)
        truck = orders.get("truck")
        if isinstance(truck, dict) and truck.get("type"):
            run(lambda: actions.buy_truck(runner, state, fid, truck["type"], truck.get("mode", "buy"), year, day))
        stock = orders.get("stock")
        if isinstance(stock, dict):
            if self.depot is None:
                self.depot = actions.Depot()
            for target, shares in (stock.get("sell") or {}).items():
                run(lambda t=target, n=shares: self.depot.sell(runner, fid, t, float(n)))
            for target, shares in (stock.get("buy") or {}).items():
                run(lambda t=target, n=shares: self.depot.buy(runner, fid, t, float(n)))

    def _apply_contract_orders(self, orders: dict, run) -> None:
        """Lieferverträge: contract_propose / contract_accept / contract_decline / contract_cancel."""
        runner, fid = self.runner, self._firm_id
        book = getattr(runner, "contracts", None)
        wanted = ("contract_propose", "contract_accept", "contract_decline", "contract_cancel",
                  "contract_change_propose", "contract_change_accept", "contract_change_decline")
        if not any(orders.get(key) for key in wanted):
            return

        def call(function):
            if book is None:
                return {"ok": False, "message": "Lieferverträge sind noch nicht verfügbar"}
            try:
                return function()
            except ValueError as exc:
                return {"ok": False, "message": str(exc)}

        propose = orders.get("contract_propose")
        if isinstance(propose, dict) and propose.get("partner"):
            def do_propose():
                partner = propose["partner"]
                role = None
                for item in book.partners(fid):
                    if item.get("id") == partner:
                        role = item.get("role")
                if role is None:
                    return {"ok": False, "message": "Mit dieser Firma ist kein Liefervertrag möglich"}
                supplier, buyer = (fid, partner) if role == "Kunde" else (partner, fid)
                book.propose_bottles(supplier, buyer, float(propose["units_per_day"]),
                                     float(propose["price"]), int(propose["days"]),
                                     propose.get("category") or None, fid)
                return {"ok": True, "message": "Vertragsvorschlag wurde gemacht"}
            run(lambda: call(do_propose))
        change = orders.get("contract_change_propose")
        for item in (change if isinstance(change, list) else [change]):
            if isinstance(item, dict) and item.get("id") not in (None, ""):
                def do_change(item=item):
                    units, price, days = item.get("units_per_day"), item.get("price"), item.get("days")
                    book.propose_change_bottles(
                        int(item["id"]), fid,
                        None if units in (None, "") else float(units),
                        None if price in (None, "") else float(price),
                        None if days in (None, "") else int(days))
                    return {"ok": True, "message": "Vertragsanpassung wurde vorgeschlagen"}
                run(lambda do_change=do_change: call(do_change))
        for key, method, text in (("contract_change_accept", "accept_change", "Vertragsanpassung wurde angenommen"),
                                  ("contract_change_decline", "decline_change", "Vertragsanpassung wurde abgelehnt"),
                                  ("contract_accept", "accept", "Vertrag wurde angenommen"),
                                  ("contract_decline", "decline", "Vertrag wurde abgelehnt"),
                                  ("contract_cancel", "cancel", "Vertrag wurde gekündigt")):
            value = orders.get(key)
            if value in (None, "", False):
                continue
            ids = value if isinstance(value, list) else [value]
            for contract_id in ids:
                def do(contract_id=contract_id, method=method, text=text):
                    getattr(book, method)(int(contract_id))
                    return {"ok": True, "message": text}
                run(lambda do=do: call(do))

    def _holding_upkeep(self, year: int, day: int, upkeep: bool = True) -> None:
        """Aktualisiert CEOs, Tendenzen und Lohnkosten der Holding-Töchter."""

        runner = self.runner
        state = self._state
        dpy = runner.config.simulation.days_per_year
        global_day = int(getattr(runner.env, "period", 0))
        days_since_halt = (
            0 if self._last_halt_day is None
            else max(0, global_day - self._last_halt_day)
        )

        if not upkeep:
            # Nach den Aufträgen nur die Führungsart sofort anpassen.
            for firm_id in holding_player.daughters(runner, self._firm_id):
                avatar = self.ceo_book.ceo_of(firm_id)
                runner.network.firm(firm_id).tendency = (
                    STYLE_TENDENCY[avatar.style] if avatar is not None else CAUTIOUS_TENDENCY)
            return
        for firm_id, avatar in self.ceo_book.retire_due(year, day, dpy):
            firm = runner.network.firm(firm_id)
            state.events.append({
                "year": year,
                "day": day,
                "firm": self._firm_id,
                "event": "ceo_retired",
                "details": f"{avatar.name} geht in Pension. {firm.name} braucht einen neuen CEO.",
            })

        for firm_id in holding_player.daughters(runner, self._firm_id):
            firm = runner.network.firm(firm_id)
            avatar = self.ceo_book.ceo_of(firm_id)
            if avatar is not None:
                firm.tendency = STYLE_TENDENCY[avatar.style]
                salary = avatar.salary * days_since_halt / dpy
                if salary:
                    runner.env.runtimes[firm_id].adjust_cash(-salary, "ceo_lohn")
            else:
                firm.tendency = CAUTIOUS_TENDENCY
                state.events.append({
                    "year": year,
                    "day": day,
                    "firm": self._firm_id,
                    "event": "ceo_missing",
                    "details": f"{firm.name} hat keinen CEO und läuft vorsichtig auf Autopilot.",
                })

        self._last_halt_day = global_day

    def _wait(self) -> RoundSnapshot:
        """Wartet auf einen Snapshot oder das Ende der Simulation."""

        item = self._to_main.get()
        if isinstance(item, RoundSnapshot):
            if item.game_over:
                self.finished = True
                self._holding = False
            else:
                self._holding = True
            return item

        kind, value = item
        if kind == "error":
            self.finished = True
            self._holding = False
            raise value
        if kind == "done":
            self.finished = True
            self._holding = False
            self.result = value
            if self._firm_id is not None and not self.runner.env.runtimes[self._firm_id].active:
                reason = "konkurs"
            else:
                reason = self._reason or "ende"
            return self._snapshot(
                self.runner,
                self._state,
                self._last_year,
                self._last_day,
                game_over=True,
                reason=reason,
            )
        raise RuntimeError(f"Unbekannte Nachricht aus dem Simulationsthread: {kind}")

    def _snapshot(
        self,
        runner: SimulationRunner,
        state: RunState,
        year: int,
        day: int,
        game_over: bool = False,
        reason: str | None = None,
    ) -> RoundSnapshot:
        """Baut einen Snapshot aus dem aktuellen oder letzten bekannten Zustand."""

        firm_id = self._firm_id
        firm = self._current_firm()
        runtime = runner.env.runtimes[firm_id]
        rival_prices = [
            other.sell_price
            for other in runner.network.firms_in(firm.stage)
            if other.id != firm_id and runner.env.runtimes[other.id].active
        ]
        events = [dict(event) for event in state.events[self._event_mark:]]
        self._event_mark = len(state.events)
        policy = runner.policies[firm_id]
        if isinstance(policy, PlayerPolicy):
            self._settings = policy.settings
        settings = replace(self._settings)
        days_per_month = runner.config.workforce.days_per_month

        return RoundSnapshot(
            year=year,
            month=day // days_per_month + 1,
            firm_id=firm_id,
            name=firm.name,
            cash=runtime.cash,
            inventory=runtime.inventory,
            backlog=runtime.backlog,
            employees=runtime.employees,
            sell_price=firm.sell_price,
            profit=runtime.profit,
            recent_demand=runner._moving_average(state.recent_demand[firm_id], 1.0),
            recent_sales=runner._moving_average(state.recent_sales[firm_id], 0.0),
            rival_price=sum(rival_prices) / len(rival_prices) if rival_prices else None,
            events=events,
            settings=settings,
            game_over=game_over,
            reason=reason,
        )

    def _current_firm(self):
        """Gibt die aktuelle Netzwerkfirma oder die gespeicherte Vorlage zurück."""

        find_firm = getattr(self.runner.network, "firm", None)
        if callable(find_firm):
            try:
                return find_firm(self._firm_id)
            except (KeyError, ValueError):
                pass
        return self._firm
