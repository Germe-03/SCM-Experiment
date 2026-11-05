"""Phase 24: one research tree per sector; every firm has its own progress (research, then implementation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_sim.config import ResearchStageConfig
from market_sim.kpi import PROJECT_DE, chf
from market_sim.research import ResearchLab

if TYPE_CHECKING:
    from market_sim.runner import RunState, SimulationRunner


def tree_key(firm) -> str:
    """Return the research tree key for a firm."""
    return "restaurant" if firm.stage == "retailer" and firm.channel == "restaurant" else firm.stage


class ResearchTreeLab(ResearchLab):
    """Run research and implementation projects in firm-specific sector trees."""

    def __init__(self, runner: SimulationRunner, seed: int) -> None:
        super().__init__(runner, seed)
        self.stages: dict[str, dict[str, ResearchStageConfig]] = {
            tree: {stage.name: stage for stage in stages}
            for tree, stages in self.cfg.trees.items()
        }
        self.progress: dict[str, dict[str, str]] = {}
        self.first_success: dict[tuple[str, str], int] = {}
        self.running: dict[str, tuple[str, int, int, float, int, str, str]] = {}

    def daily(self, env) -> None:
        for firm_id, (_, _, end, daily_cost, _, _, _) in self.running.items():
            runtime = env.runtimes[firm_id]
            if runtime.active and env.period <= end:
                runtime.rnd_spend += daily_cost
                self.stats["rnd_project_spend"] += daily_cost

    def available(self, firm, stage: ResearchStageConfig) -> bool:
        """Return whether a firm can use a stage."""
        return (
            stage.enabled
            and (not stage.categories or firm.category in stage.categories)
            and (stage.kind != "maturation" or not firm.importer)
        )

    def requirements_met(self, firm, tree: str, stage: ResearchStageConfig) -> bool:
        """Return whether a stage's reachable prerequisites are implemented."""
        progress = self.progress.get(firm.id, {})
        tree_stages = self.stages[tree]
        return all(
            progress.get(name) == "implemented"
            or name not in tree_stages
            or not self.available(firm, tree_stages[name])
            for name in stage.requires
        )

    def research_cost(self, tree: str, stage: ResearchStageConfig, year: int) -> float:
        """Return the stage's cost, discounted for followers."""
        if (tree, stage.name) in self.first_success:
            return stage.cost * (1 - self.cfg.follower_discount.get(stage.complexity, 0.0))
        return stage.cost

    def options(self, firm) -> list[ResearchStageConfig]:
        """Return available stages whose prerequisites are met."""
        tree = tree_key(firm)
        progress = self.progress.get(firm.id, {})
        return [
            stage
            for stage in self.stages.get(tree, {}).values()
            if self.available(firm, stage)
            and progress.get(stage.name) not in ("researched", "implemented")
            and self.requirements_met(firm, tree, stage)
        ]

    def transfer(self, seller_id: str, buyer_id: str) -> None:
        """Transfer researched knowledge from a seller to a buyer."""
        seller_progress = self.progress.get(seller_id, {})
        buyer_progress = self.progress.setdefault(buyer_id, {})
        for name in sorted(seller_progress):
            if seller_progress[name] in ("researched", "implemented") and buyer_progress.get(name) not in (
                "researched",
                "implemented",
            ):
                buyer_progress[name] = "researched"
        self.running.pop(seller_id, None)

    def year_end(self, runner: SimulationRunner, state: RunState) -> None:
        env = runner.env
        days = runner.config.simulation.days_per_year
        price = runner.long_run.price_index

        for firm_id in sorted(self.running):
            name, start, end, daily_cost, start_year, step, tree = self.running[firm_id]
            if env.period < end:
                continue
            del self.running[firm_id]
            roll = self.rng.random()
            if not env.runtimes[firm_id].active:
                continue

            firm = runner.network.firm(firm_id)
            stage = self.stages[tree][name]
            label = PROJECT_DE.get(name, name)
            if step == "research":
                success = roll < stage.success_probability
                if success:
                    self.progress.setdefault(firm_id, {})[name] = "researched"
                    self.first_success.setdefault((tree, name), state.year)
                    self.stats["rnd_successes"] += 1
                    event = "rnd_success"
                    detail = "erforscht"
                    event_detail = f"{label}: erforscht, Umsetzung folgt"
                else:
                    self.stats["rnd_failures"] += 1
                    event = "rnd_failure"
                    detail = "kein Ergebnis"
                    event_detail = f"{label}: kein Ergebnis"
                self.reports.append({
                    "firm": firm_id,
                    "project": name,
                    "tree": tree,
                    "step": "research",
                    "start_year": start_year,
                    "end_year": state.year,
                    "cost": daily_cost * (end - start),
                    "success": success,
                    "result": detail,
                })
                state.events.append({
                    "year": state.year,
                    "day": days,
                    "firm": firm_id,
                    "event": event,
                    "details": event_detail,
                })
            else:
                detail = self._apply_stage(runner, firm, stage)
                self.progress.setdefault(firm_id, {})[name] = "implemented"
                self.reports.append({
                    "firm": firm_id,
                    "project": name,
                    "tree": tree,
                    "step": "implementation",
                    "start_year": start_year,
                    "end_year": state.year,
                    "cost": daily_cost * (end - start),
                    "success": True,
                    "result": detail,
                })
                state.events.append({
                    "year": state.year,
                    "day": days,
                    "firm": firm_id,
                    "event": "rnd_implemented",
                    "details": f"{label}: umgesetzt, {detail}",
                })

        summaries = state.summaries[-1]
        for firm in runner._firms():
            choice_roll = self.rng.random()
            runtime = env.runtimes[firm.id]
            if (
                not self.cfg.enabled
                or not runtime.active
                or firm.id in self.running
                or firm.id not in summaries
            ):
                continue
            if summaries[firm.id].profit <= 0:
                continue

            tree = tree_key(firm)
            pending = [
                stage
                for stage in self.stages.get(tree, {}).values()
                if self.progress.get(firm.id, {}).get(stage.name) == "researched"
            ]
            if pending:
                stage = pending[0]
                label = PROJECT_DE.get(stage.name, stage.name)
                cost = stage.implementation_cost * price
                if runtime.cash >= self.cfg.cash_cover * cost and (
                    cost <= 0 or env.can_spend(firm.id, cost)
                ):
                    self.running[firm.id] = (
                        stage.name,
                        env.period,
                        env.period + stage.implementation_days,
                        cost / stage.implementation_days,
                        state.year,
                        "implementation",
                        tree,
                    )
                    state.events.append({
                        "year": state.year,
                        "day": days,
                        "firm": firm.id,
                        "event": "rnd_started",
                        "details": (
                            f"Umsetzung {label}, Kosten {chf(cost)}, "
                            f"{stage.implementation_days} Tage"
                        ),
                    })
                continue

            options = self.options(firm)
            preferred_branches = self.cfg.branch_preferences.get(firm.archetype, [])
            preferred = [stage for stage in options if stage.branch in preferred_branches]
            pool = preferred or options
            if not pool or choice_roll >= self.cfg.start_probability:
                continue

            target = choice_roll / self.cfg.start_probability * sum(
                stage.selection_weight for stage in pool
            )
            stage = pool[-1]
            for candidate in pool:
                target -= candidate.selection_weight
                if target < 0:
                    stage = candidate
                    break

            cost = self.research_cost(tree, stage, state.year) * price
            if runtime.cash < self.cfg.cash_cover * cost:
                continue
            if cost > 0 and not env.can_spend(firm.id, cost):
                continue

            self.running[firm.id] = (
                stage.name,
                env.period,
                env.period + stage.duration_days,
                cost / stage.duration_days,
                state.year,
                "research",
                tree,
            )
            self.stats["rnd_started"] += 1
            label = PROJECT_DE.get(stage.name, stage.name)
            details = f"{label}, Kosten {chf(cost)}, {stage.duration_days} Tage"
            if (
                (tree, stage.name) in self.first_success
                and self.cfg.follower_discount.get(stage.complexity, 0.0) > 0
            ):
                details += " (Nachzügler-Rabatt)"
            state.events.append({
                "year": state.year,
                "day": days,
                "firm": firm.id,
                "event": "rnd_started",
                "details": details,
            })

    def _apply_stage(self, runner: SimulationRunner, firm, stage: ResearchStageConfig) -> str:
        """Apply a newly implemented tree stage."""
        if stage.kind == "reputation":
            before = firm.reputation
            firm.reputation = min(1.0, before + stage.effect)
            return f"Reputation +{stage.effect:.0%}"
        if stage.kind == "awareness":
            book = runner.env.brand_book
            if book is None:
                return "kein Markenmarkt"
            aware = book.store_awareness.get(firm.id, runner.config.marketing.start_awareness)
            book.store_awareness[firm.id] = aware + (1 - aware) * stage.effect
            return f"Bekanntheit des Ladens +{stage.effect:.0%}"
        if stage.kind == "margin":
            book = runner.env.brand_book
            if book is None:
                return "kein Markenmarkt"
            bonus = getattr(book, "markup_bonus", None)
            if bonus is None:
                book.markup_bonus = bonus = {}
            bonus[firm.id] = bonus.get(firm.id, 1.0) * (1 + stage.effect)
            return f"Marge im Lokal +{stage.effect:.0%}"
        if stage.kind == "maturation":
            book = runner.env.brand_book
            if book is None:
                return "kein Markenmarkt"
            for brand_id in book.brands_of(firm.id):
                brand = book.brands[brand_id]
                if brand.maturation_days > 0:
                    brand.maturation_days = max(
                        1,
                        round(brand.maturation_days * (1 - stage.effect)),
                    )
            return f"Reifezeit −{stage.effect:.0%}"
        return self._apply(runner, firm, stage)
