"""Phase 40: holdings with separate active subsidiaries and consolidated finances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from market_sim.kpi import chf

if TYPE_CHECKING:
    from market_sim.models import Firm
    from market_sim.runner import RunState, SimulationRunner


@dataclass
class HoldingGroup:
    id: str
    name: str
    root_id: str
    listing_id: str
    subs: list[str]
    cash: float = 0.0
    founded_year: int = 0
    dissolved_year: int | None = None
    successor: str | None = None
    reason: str = ""


class HoldingGroups:
    """Manage holding groups, their subsidiaries and reserve sweeps."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.holding_groups
        self.groups: dict[str, HoldingGroup] = {}
        self.sub_of: dict[str, str] = {}
        self.listing_group: dict[str, str] = {}
        self.listing_owner: dict[str, str] = {}
        self.history: list[dict[str, object]] = []
        self._no_cover_events: set[tuple[str, str, int]] = set()
        self.stats = {
            "holdings_formed": 0,
            "subsidiaries_bought": 0,
            "swept": 0.0,
            "sweep_tax": 0.0,
            "covered": 0.0,
            "uncovered": 0,
            "subsidiaries_sold": 0,
            "holdings_bought": 0,
            "holdings_dissolved": 0,
        }

    def group_of(self, firm_id: str) -> HoldingGroup | None:
        group_id = self.sub_of.get(firm_id)
        group = self.groups.get(group_id) if group_id is not None else None
        return group if group is not None and group.dissolved_year is None else None

    def is_sub_only(self, firm_id: str) -> bool:
        group = self.group_of(firm_id)
        return group is not None and firm_id != group.listing_id

    def listing_alive(self, listing_id: str) -> bool:
        group_id = self.listing_group.get(listing_id)
        group = self.groups.get(group_id) if group_id is not None else None
        return group is not None and group.dissolved_year is None

    def owner_of_listing(self, listing_id: str) -> str:
        return self.listing_owner.get(listing_id, listing_id)

    def active_subs(self, runner: SimulationRunner, group: HoldingGroup) -> list[str]:
        return [firm_id for firm_id in group.subs if runner.env.runtimes[firm_id].active]

    def avg_revenue(self, state: RunState, firm_id: str) -> float:
        summaries = [year[firm_id] for year in state.summaries if firm_id in year]
        revenues = [summary.revenue for summary in summaries[-self.cfg.reserve_years:]]
        return sum(revenues) / len(revenues) if revenues else 0.0

    def reserve_target(self, state: RunState, firm_id: str) -> float:
        return self.cfg.reserve_share * self.avg_revenue(state, firm_id)

    def _ensure_group(self, buyer: Firm, year: int) -> HoldingGroup:
        """Return the buyer's group, creating a holding for a standalone buyer."""
        group = self.group_of(buyer.id)
        if group is not None:
            return group

        group = HoldingGroup(
            id=f"holding_{buyer.id}",
            name=f"{buyer.name} Holding",
            root_id=buyer.id,
            listing_id=buyer.id,
            subs=[buyer.id],
            founded_year=year,
        )
        self.groups[group.id] = group
        self.sub_of[buyer.id] = group.id
        self.listing_group[group.listing_id] = group.id
        self.stats["holdings_formed"] += 1
        return group

    def acquire(
        self,
        runner: SimulationRunner,
        state: RunState,
        buyer: Firm,
        target: Firm,
        price: float,
        year: int,
        day: int,
    ) -> bool:
        buyer_group = self.group_of(buyer.id)
        if target.id in self.sub_of or buyer.id == target.id:
            return False
        if buyer_group is not None and target.id in buyer_group.subs:
            return False

        buyer_runtime = runner.env.runtimes[buyer.id]
        available = buyer_runtime.cash + (buyer_group.cash if buyer_group is not None else 0.0)
        if available < price:
            return False

        from_group = min(price, buyer_group.cash) if buyer_group is not None else 0.0
        if buyer_group is not None:
            buyer_group.cash -= from_group
        rest = price - from_group
        if rest:
            buyer_runtime.adjust_cash(-rest, f"uebernahme:{target.id}")

        if buyer_group is None:
            group = self._ensure_group(buyer, year)
            group.subs.append(target.id)
            self.sub_of[target.id] = group.id
            details = (
                f"{buyer.name} übernimmt {target.name} für {chf(price)}: {group.name} "
                "gegründet, beide Firmen bleiben als Töchter bestehen"
            )
            event = "holding_formed"
            action = "formed"
        else:
            group = buyer_group
            group.subs.append(target.id)
            self.sub_of[target.id] = group.id
            details = f"{group.name} kauft Tochter {target.name} für {chf(price)}"
            event = "holding_acquisition"
            self.stats["subsidiaries_bought"] += 1
            action = "acquired"

        state.events.append({
            "year": year, "day": day, "firm": buyer.id, "event": event, "details": details,
        })
        self.history.append({
            "year": year, "holding": group.id, "action": action,
            "firm": target.id, "amount": price, "details": details,
        })
        runner.decision_log.record(
            year, buyer.id, "takeover_bought",
            {"target": target.id, "price": price, "holding": group.id},
            "Übernahme eines finanziell angeschlagenen Konkurrenten als Tochter einer Holding",
        )
        if runner.state_actor is not None:
            runner.state_actor.stats["takeovers"] += 1
        return True

    def fundamental_inputs(
        self, runner: SimulationRunner, state: RunState, listing_id: str
    ) -> tuple[float, float] | None:
        group_id = self.listing_group.get(listing_id)
        group = self.groups.get(group_id) if group_id is not None else None
        if group is None or group.dissolved_year is not None:
            return None

        mean_profit = 0.0
        for firm_id in group.subs:
            summaries = [year[firm_id] for year in state.summaries if firm_id in year][-2:]
            profits = [summary.profit for summary in summaries]
            if profits:
                mean_profit += sum(profits) / len(profits)
        cash = group.cash + sum(
            max(0.0, runner.env.runtimes[firm_id].cash)
            for firm_id in group.subs if runner.env.runtimes[firm_id].active
        )
        return mean_profit, cash

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        year = state.year
        day = runner.config.simulation.days_per_year

        for group in (self.groups[key] for key in sorted(self.groups)):
            if group.dissolved_year is not None:
                continue
            retained = []
            for firm_id in group.subs:
                if runner.env.runtimes[firm_id].active:
                    retained.append(firm_id)
                    continue
                if self.sub_of.get(firm_id) == group.id:
                    del self.sub_of[firm_id]
                name = runner.network.firm(firm_id).name
                details = f"{name} ist nicht mehr Tochter von {group.name} (geschlossen)"
                state.events.append({
                    "year": year, "day": day, "firm": firm_id,
                    "event": "holding_daughter_lost", "details": details,
                })
            group.subs = retained

        for group in (self.groups[key] for key in sorted(self.groups)):
            if group.dissolved_year is not None:
                continue
            total_swept = 0.0
            total_tax = 0.0
            for firm_id in group.subs:
                runtime = runner.env.runtimes[firm_id]
                if not runtime.active:
                    continue
                if self.avg_revenue(state, firm_id) == 0:
                    continue
                excess = runtime.cash - self.reserve_target(state, firm_id)
                if excess <= 0:
                    continue
                tax = excess * self.cfg.sweep_tax
                runtime.adjust_cash(-excess, f"holding:{group.id}")
                group.cash += excess - tax
                if runner.state_actor is not None:
                    runner.state_actor.stats["taxes"] += tax
                self.stats["swept"] += excess
                self.stats["sweep_tax"] += tax
                total_swept += excess
                total_tax += tax
            if total_swept > 0:
                state.events.append({
                    "year": year,
                    "day": day,
                    "firm": group.root_id,
                    "event": "holding_sweep",
                    "details": (
                        f"Reserve-Abschöpfung: {chf(total_swept)} an {group.name}, "
                        f"Steuer {chf(total_tax)}"
                    ),
                })

        self.after_sweep(runner, state, year)

    def after_sweep(self, runner: SimulationRunner, state: RunState, year: int) -> None:
        day = runner.config.simulation.days_per_year
        summaries = state.summaries[-1] if state.summaries else {}

        for group in (self.groups[key] for key in sorted(self.groups)):
            if group.dissolved_year is not None:
                continue

            active_subs = self.active_subs(runner, group)
            total_rev = sum(
                summaries[firm_id].revenue for firm_id in active_subs if firm_id in summaries
            )
            for firm_id in active_subs:
                runtime = runner.env.runtimes[firm_id]
                avg = self.avg_revenue(state, firm_id)
                floor = self.cfg.min_reserve_share * avg
                if runtime.cash >= floor or avg <= 0:
                    continue

                need = floor - runtime.cash
                duty = group.cash >= self.cfg.cover_cash_share * total_rev
                if duty:
                    if group.cash <= 0:
                        continue
                    pay = min(need, group.cash)
                    runtime.adjust_cash(pay, f"holding_zuschuss:{group.id}")
                    group.cash -= pay
                    details = (
                        f"{group.name} füllt die Reserve von "
                        f"{runner.network.firm(firm_id).name} um {chf(pay)} auf"
                    )
                    state.events.append({
                        "year": year,
                        "day": day,
                        "firm": firm_id,
                        "event": "holding_cover",
                        "details": details,
                    })
                    self.stats["covered"] += pay
                    self.history.append({
                        "year": year,
                        "holding": group.id,
                        "action": "covered",
                        "firm": firm_id,
                        "amount": pay,
                        "details": details,
                    })
                else:
                    key = (group.id, firm_id, year)
                    if key in self._no_cover_events:
                        continue
                    self._no_cover_events.add(key)
                    details = (
                        f"{group.name} stützt {runner.network.firm(firm_id).name} "
                        "nicht mehr, Konkurs möglich"
                    )
                    state.events.append({
                        "year": year,
                        "day": day,
                        "firm": firm_id,
                        "event": "holding_no_cover",
                        "details": details,
                    })
                    self.stats["uncovered"] += 1

            if len(self.active_subs(runner, group)) <= 2:
                continue
            for firm_id in group.subs:
                if firm_id == group.listing_id or not runner.env.runtimes[firm_id].active:
                    continue
                if runner.env.runtimes[firm_id].consecutive_loss_years < self.cfg.sale_loss_years:
                    continue
                price = self.cfg.sale_revenue_factor * self.avg_revenue(state, firm_id)
                firm = runner.network.firm(firm_id)
                details = f"{group.name} verkauft Tochter {firm.name} für {chf(price)}"
                group.cash += price
                group.subs.remove(firm_id)
                if self.sub_of.get(firm_id) == group.id:
                    del self.sub_of[firm_id]
                state.events.append({
                    "year": year,
                    "day": day,
                    "firm": firm_id,
                    "event": "holding_sold",
                    "details": details,
                })
                self.stats["subsidiaries_sold"] += 1
                self.history.append({
                    "year": year,
                    "holding": group.id,
                    "action": "sold",
                    "firm": firm_id,
                    "amount": price,
                    "details": details,
                })
                break

        takeover_done = False
        if self.cfg.holding_takeovers:
            for group in (self.groups[key] for key in sorted(self.groups)):
                if takeover_done:
                    break
                if group.dissolved_year is not None:
                    continue
                active_subs = self.active_subs(runner, group)
                if not active_subs:
                    continue
                total_cash = group.cash + sum(
                    runner.env.runtimes[firm_id].cash for firm_id in active_subs
                )
                if total_cash >= 0:
                    continue

                candidates = []
                for firm in runner._firms():
                    runtime = runner.env.runtimes[firm.id]
                    summary = summaries.get(firm.id)
                    if (
                        not runtime.active
                        or summary is None
                        or summary.profit <= 0
                        or self.group_of(firm.id) is group
                    ):
                        continue
                    if not any(
                        runner.network.firm(sub_id).stage == firm.stage
                        and runner.network.firm(sub_id).category == firm.category
                        and runner.network.firm(sub_id).channel == firm.channel
                        for sub_id in active_subs
                    ):
                        continue
                    candidates.append(firm)

                candidates.sort(
                    key=lambda firm: (-runner.env.runtimes[firm.id].cash, firm.id)
                )
                for buyer in candidates:
                    buyer_group = self.group_of(buyer.id)
                    buyer_group_subs = (
                        self.active_subs(runner, buyer_group) if buyer_group is not None else []
                    )
                    relevant_ids = {buyer.id}
                    relevant_ids.update(buyer_group_subs)
                    relevant_ids.update(
                        sub_id for sub_id in active_subs
                        if runner.network.firm(sub_id).stage == buyer.stage
                    )
                    numerator = sum(
                        summaries[firm_id].revenue
                        for firm_id in sorted(relevant_ids)
                        if firm_id in summaries
                        and runner.network.firm(firm_id).stage == buyer.stage
                    )
                    denominator = sum(
                        summaries[firm.id].revenue
                        for firm in runner._firms()
                        if runner.env.runtimes[firm.id].active
                        and firm.id in summaries
                        and firm.stage == buyer.stage
                    )
                    combined = numerator / (denominator or 1.0)
                    if combined > runner.config.state.block_share:
                        details = (
                            f"Holding {group.name}, gemeinsamer Marktanteil {combined:.0%}"
                        )
                        state.events.append({
                            "year": year,
                            "day": day,
                            "firm": buyer.id,
                            "event": "takeover_blocked",
                            "details": details,
                        })
                        if runner.state_actor is not None:
                            runner.state_actor.stats["takeovers_blocked"] += 1
                        continue

                    capacity = sum(
                        runner.env._effective_capacity(sub_id) for sub_id in active_subs
                    )
                    price = max(
                        0.0,
                        runner.config.state.price_per_capacity_unit
                        * runner.long_run.price_index
                        * capacity
                        + group.cash
                        + sum(runner.env.runtimes[sub_id].cash for sub_id in active_subs),
                    )
                    buyer_cash = runner.env.runtimes[buyer.id].cash
                    buyer_group_cash = buyer_group.cash if buyer_group is not None else 0.0
                    if (
                        buyer_cash + buyer_group_cash < price
                        or not runner.env.can_spend(buyer.id, price)
                    ):
                        continue

                    from_group = min(price, max(0.0, buyer_group_cash))
                    if buyer_group is not None:
                        buyer_group.cash -= from_group
                    rest = price - from_group
                    if rest:
                        runner.env.runtimes[buyer.id].adjust_cash(
                            -rest, f"uebernahme:{group.id}"
                        )

                    buyer_group = self._ensure_group(buyer, year)
                    moved_subs = list(active_subs)
                    for sub_id in moved_subs:
                        if sub_id not in buyer_group.subs:
                            buyer_group.subs.append(sub_id)
                        self.sub_of[sub_id] = buyer_group.id
                    if group.cash > 0:
                        buyer_group.cash += group.cash

                    n = len(moved_subs)
                    details = (
                        f"{buyer_group.name} kauft {group.name} samt {n} Töchtern "
                        f"für {chf(price)}"
                    )
                    group.dissolved_year = year
                    group.successor = buyer_group.id
                    group.reason = "gekauft"
                    self.listing_group.pop(group.listing_id, None)
                    group.subs = []
                    group.cash = 0.0
                    state.events.append({
                        "year": year,
                        "day": day,
                        "firm": buyer.id,
                        "event": "holding_takeover",
                        "details": details,
                    })
                    self.stats["holdings_bought"] += 1
                    self.history.append({
                        "year": year,
                        "holding": group.id,
                        "action": "bought",
                        "firm": buyer.id,
                        "amount": price,
                        "details": details,
                    })
                    if runner.state_actor is not None:
                        runner.state_actor.stats["takeovers"] += 1
                    takeover_done = True
                    break

        for group in (self.groups[key] for key in sorted(self.groups)):
            if group.dissolved_year is not None:
                continue
            active_subs = self.active_subs(runner, group)
            if len(active_subs) not in (0, 1):
                continue

            cash = group.cash
            remaining = active_subs[0] if active_subs else None
            if remaining is not None:
                runtime = runner.env.runtimes[remaining]
                if cash != 0:
                    runtime.adjust_cash(cash, f"holding_aufgeloest:{group.id}")
                group.successor = remaining
                group.reason = "eine Tochter übrig"
                remaining_firm = runner.network.firm(remaining)
                details = (
                    f"{group.name} aufgelöst: {remaining_firm.name} erhält {chf(cash)}, "
                    "Aktien 1:1 zurück, Börsenverlauf läuft weiter"
                )
                state.events.append({
                    "year": year,
                    "day": day,
                    "firm": remaining,
                    "event": "holding_dissolved",
                    "details": details,
                })
                self.listing_owner[group.listing_id] = remaining
            else:
                group.successor = None
                group.reason = "keine Töchter übrig"
                details = f"{group.name} aufgelöst: keine Töchter übrig"

            group.cash = 0.0
            group.dissolved_year = year
            for firm_id in group.subs:
                self.sub_of.pop(firm_id, None)
            self.listing_group.pop(group.listing_id, None)
            group.subs = []
            self.stats["holdings_dissolved"] += 1
            self.history.append({
                "year": year,
                "holding": group.id,
                "action": "dissolved",
                "firm": remaining,
                "amount": cash,
                "details": details,
            })

    def snapshot(
        self, runner: SimulationRunner, state: RunState, year: int
    ) -> list[dict[str, object]]:
        last_summary = state.summaries[-1] if state.summaries else {}
        rows = []
        for group_id in sorted(self.groups):
            group = self.groups[group_id]
            subsidiaries = []
            for firm_id in group.subs:
                firm = runner.network.firm(firm_id)
                runtime = runner.env.runtimes[firm_id]
                summary = last_summary.get(firm_id)
                avg = self.avg_revenue(state, firm_id)
                subsidiaries.append({
                    "firm": firm_id,
                    "name": firm.name,
                    "active": runtime.active,
                    "cash": runtime.cash,
                    "reserve": self.reserve_target(state, firm_id),
                    "reserve_floor": self.cfg.min_reserve_share * avg,
                    "revenue": summary.revenue if summary is not None else 0.0,
                    "profit": summary.profit if summary is not None else 0.0,
                })
            rows.append({
                "year": year,
                "holding": group.id,
                "name": group.name,
                "listing_id": group.listing_id,
                "status": "dissolved" if group.dissolved_year is not None else "active",
                "founded_year": group.founded_year,
                "dissolved_year": group.dissolved_year,
                "successor": group.successor,
                "cash": group.cash,
                "subs": subsidiaries,
            })
        return rows

    def report(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.history]
