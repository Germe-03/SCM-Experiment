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
        self.stats = {
            "holdings_formed": 0, "subsidiaries_bought": 0, "swept": 0.0, "sweep_tax": 0.0,
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

    def active_subs(self, runner: SimulationRunner, group: HoldingGroup) -> list[str]:
        return [firm_id for firm_id in group.subs if runner.env.runtimes[firm_id].active]

    def avg_revenue(self, state: RunState, firm_id: str) -> float:
        summaries = [year[firm_id] for year in state.summaries if firm_id in year]
        revenues = [summary.revenue for summary in summaries[-self.cfg.reserve_years:]]
        return sum(revenues) / len(revenues) if revenues else 0.0

    def reserve_target(self, state: RunState, firm_id: str) -> float:
        return self.cfg.reserve_share * self.avg_revenue(state, firm_id)

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
            group = HoldingGroup(
                id=f"holding_{buyer.id}",
                name=f"{buyer.name} Holding",
                root_id=buyer.id,
                listing_id=buyer.id,
                subs=[buyer.id, target.id],
                founded_year=year,
            )
            self.groups[group.id] = group
            self.sub_of[buyer.id] = group.id
            self.sub_of[target.id] = group.id
            self.listing_group[group.listing_id] = group.id
            details = (
                f"{buyer.name} übernimmt {target.name} für {chf(price)}: {group.name} "
                "gegründet, beide Firmen bleiben als Töchter bestehen"
            )
            event = "holding_formed"
            self.stats["holdings_formed"] += 1
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
        return

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
                subsidiaries.append({
                    "firm": firm_id,
                    "name": firm.name,
                    "active": runtime.active,
                    "cash": runtime.cash,
                    "reserve": self.reserve_target(state, firm_id),
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
