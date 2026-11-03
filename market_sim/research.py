"""Phase 7: research and development projects with cost, duration and an uncertain outcome."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from market_sim.brands import Brand
from market_sim.kpi import PROJECT_DE, chf

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


class ResearchLab:
    """Runs at most one project per firm; costs are booked daily while it runs."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        self.cfg = runner.config.research
        self.rng = random.Random(f"research-{seed}")
        self.projects = {p.name: p for p in self.cfg.projects}
        # Running projects: firm id -> (project name, start day, end day, daily cost, start year).
        self.running: dict[str, tuple[str, int, int, float, int]] = {}
        self.reports: list[dict[str, object]] = []
        self.stats = {"rnd_started": 0, "rnd_successes": 0, "rnd_failures": 0, "rnd_project_spend": 0.0}
        self._brands = 0

    def daily(self, env) -> None:
        for firm_id, (_, _, end, daily_cost, _) in self.running.items():
            runtime = env.runtimes[firm_id]
            if runtime.active and env.period <= end:
                runtime.rnd_spend += daily_cost
                self.stats["rnd_project_spend"] += daily_cost

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        env = runner.env
        days = runner.config.simulation.days_per_year
        for firm_id in sorted(self.running):
            name, start, end, daily_cost, start_year = self.running[firm_id]
            if env.period < end:
                continue
            del self.running[firm_id]
            roll = self.rng.random()
            if not env.runtimes[firm_id].active:
                continue
            project = self.projects[name]
            success = roll < project.success_probability
            detail = self._apply(runner, runner.network.firm(firm_id), project) if success else "kein Ergebnis"
            self.stats["rnd_successes" if success else "rnd_failures"] += 1
            self.reports.append({"firm": firm_id, "project": name, "start_year": start_year,
                                 "end_year": state.year, "cost": daily_cost * (end - start),
                                 "success": success, "result": detail})
            state.events.append({"year": state.year, "day": days, "firm": firm_id,
                                 "event": "rnd_success" if success else "rnd_failure",
                                 "details": f"{PROJECT_DE.get(name, name)}: {detail}"})
        summaries = state.summaries[-1]
        for firm in runner._firms():
            choice_roll = self.rng.random()
            runtime = env.runtimes[firm.id]
            if not self.cfg.enabled or not runtime.active or firm.id in self.running or firm.id not in summaries:
                continue
            if summaries[firm.id].profit <= 0:
                continue
            options = [p for p in self.cfg.projects if p.enabled and firm.stage in p.stages
                       and (p.kind != "alkoholfrei" or firm.category == "beer")]
            preferred = [p for p in options if p.name in self.cfg.preferences.get(firm.archetype, [])]
            pool = preferred or options
            if not pool or choice_roll >= self.cfg.start_probability:
                continue
            target = choice_roll / self.cfg.start_probability * sum(p.selection_weight for p in pool)
            project = pool[-1]
            for candidate in pool:
                target -= candidate.selection_weight
                if target < 0:
                    project = candidate
                    break
            cost = project.cost * runner.long_run.price_index
            if runtime.cash < self.cfg.cash_cover * cost:
                continue
            self.running[firm.id] = (project.name, env.period, env.period + project.duration_days,
                                     cost / project.duration_days, state.year)
            self.stats["rnd_started"] += 1
            state.events.append({"year": state.year, "day": days, "firm": firm.id, "event": "rnd_started",
                                 "details": f"{PROJECT_DE.get(project.name, project.name)}, Kosten {chf(cost)}, "
                                            f"{project.duration_days} Tage"})

    def _apply(self, runner: SimulationRunner, firm, project) -> str:
        env = runner.env
        if project.kind == "component_reduction":
            factors = env.component_factor.setdefault(firm.id, {})
            factors[project.component] = factors.get(project.component, 1.0) * (1 - project.effect)
            component = {"malt": "Malz", "hops": "Hopfen", "packaging": "Verpackung", "energy": "Energie"}[project.component]
            return f"{component} −{project.effect:.0%}"
        if project.kind == "transport_efficiency":
            if env.geography is None:
                return "keine Transportkosten"
            factors = env.geography.transport_factor
            factors[firm.id] = factors.get(firm.id, 1.0) * (1 - project.effect)
            return f"Transportkosten −{project.effect:.0%}"
        if project.kind == "storage_automation":
            env.runtimes[firm.id].holding_cost *= 1 - project.effect
            return f"Lagerkosten −{project.effect:.0%}"
        if project.kind == "robotics":
            before = firm.employees
            firm.employees = max(1, before - round(before * project.effect))
            firm.productivity_per_employee *= before / firm.employees
            env.runtimes[firm.id].employees = firm.employees
            return f"Mitarbeitende {before} → {firm.employees}, Kapazität unverändert"
        if project.kind == "productivity":
            firm.productivity_per_employee *= 1 + project.effect
            return f"Produktivität +{project.effect:.0%}"
        if project.kind == "cost_reduction":
            env.process_cost_factor[firm.id] = env.process_cost_factor.get(firm.id, 1.0) * (1 - project.effect)
            return f"Rohstoffkosten −{project.effect:.0%}"
        book = env.brand_book
        if book is None:
            return "kein Markenmarkt"
        self._brands += 1
        brand_id = f"{firm.id}_rd{self._brands:02d}"
        if project.kind == "alkoholfrei":
            traits, positioning = ["alkoholfrei"], "standard"
        else:
            traits = ["craft"] if firm.category == "beer" else [firm.category]
            if book.entrant_trait and book.entrant_trait not in traits and firm.category == "beer":
                traits.append(book.entrant_trait)
            positioning = "premium"
        maturation = 365 if firm.category == "wine" and not firm.importer else 0
        reputation = min(1.0, firm.reputation + (project.effect if positioning == "premium" else 0.0))
        book.brands[brand_id] = Brand(brand_id, f"{firm.name} Neu {self._brands}", firm.id, positioning,
                                      reputation, traits, firm.category, maturation)
        book.production_share[brand_id] = 1.0
        return f"neue Marke {brand_id} ({', '.join(traits)})"
