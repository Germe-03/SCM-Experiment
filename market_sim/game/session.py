"""Schnittstelle für den rundenbasierten Spielmodus."""

from __future__ import annotations

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
    ) -> None:
        self.runner, _ = build_runner(years, seed, days_per_year, config)
        self.result: RunResult | None = None
        self.finished = False
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
            if branch != "hersteller":
                raise ValueError("Eine Kategorie ist nur für Hersteller erlaubt")
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
        elif stage == "factory" and category is not None:
            pool = [
                firm for firm in pool
                if firm.category == category and not firm.importer
            ]
            if not pool:
                pool = [
                    firm for firm in runner.network.firms_in(stage)
                    if runner.env.runtimes[firm.id].active
                ]

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
            "employees": max(1, round(template.employees * cfg.start_capacity_fraction)),
            "reputation": (cfg.start_reputation[0] + cfg.start_reputation[1]) / 2,
            "quality_level": template.quality_level * cfg.start_quality_fraction,
            "inventory": 0,
            "backlog": 0,
            "suppliers": [],
            "region": region or template.region,
            "extra_regions": [],
            "transport_mode": "service" if runner.config.trucks.enabled else "own",
        }
        if stage == "factory" and category is not None and template.category != category:
            updates.update(category=category, importer=False)
        firm = template.model_copy(deep=True, update=updates)

        settings = PlayerSettings.from_strategy(
            FirmPolicy().decide_annual(firm, None, runner.config)
        )
        runner.add_firm(firm, state, policy=PlayerPolicy(settings), announce=False)
        runner._entry_year[firm.id] = 0
        if not hasattr(runner, "player_choices"):
            runner.player_choices = {}
            runner.env.player_choices = runner.player_choices
        runner.player_choices[firm.id] = PlayerChoices()
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
        self._holding = False
        self._to_thread.put(("continue", None))
        self._wait()
        return SaleResult(year=year, month=month, price=price, firm_id=firm_id)

    def _run(self, state: RunState) -> None:
        """Führt die Simulation im Hintergrund aus."""

        try:
            result = self.runner.continue_run(
                state,
                self.runner.config.simulation.years,
            )
        except Exception as exc:
            self._to_main.put(("error", exc))
            return
        self._to_main.put(("done", result))

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
        if not runner.env.runtimes[firm_id].active:
            runner.day_hook = None
            return

        self._state = state
        self.state = state
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
